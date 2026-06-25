"""AI-NOC Dashboard — Backend server. Run: uvicorn server:app --reload --host 0.0.0.0 --port 8000"""

import asyncio
import contextlib
import json
import urllib.request
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import Device, Alert
from collectors.simulator import SimulatorCollector
from alerts import AlertEngine

collector = SimulatorCollector()

alert_engine = AlertEngine(
    cpu_threshold=85, mem_threshold=90,
    webhook_url=None,
)

POLL_INTERVAL = 5

# --- PASTE YOUR CLAUDE API KEY HERE TO ENABLE AI ASSIST ---
CLAUDE_API_KEY = None  # e.g. "sk-ant-api03-..."

app = FastAPI(title="AI-NOC Dashboard API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_state: List[Device] = []
_ws_clients: set = set()


async def _poll_loop() -> None:
    global _state
    await collector.startup()
    while True:
        try:
            _state = await collector.collect()
            alert_engine.evaluate(_state)
            dead = set()
            payload = [d.model_dump() for d in _state]
            for ws in _ws_clients:
                try:
                    await ws.send_json({"type": "devices", "data": payload})
                except Exception:
                    dead.add(ws)
            _ws_clients.difference_update(dead)
        except Exception as e:
            print(f"[poll] error: {e}")
        await asyncio.sleep(POLL_INTERVAL)


@app.on_event("startup")
async def _startup() -> None:
    app.state.poller = asyncio.create_task(_poll_loop())


@app.on_event("shutdown")
async def _shutdown() -> None:
    app.state.poller.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await app.state.poller
    await collector.shutdown()


# ----------------------------- REST -----------------------------
@app.get("/api/health")
async def health():
    return {"status": "ok", "source": collector.name, "devices": len(_state)}


@app.get("/api/devices", response_model=List[Device])
async def get_devices():
    return _state


@app.get("/api/devices/{device_id}", response_model=Device)
async def get_device(device_id: str):
    for d in _state:
        if d.id == device_id:
            return d
    raise HTTPException(status_code=404, detail="device not found")


@app.get("/api/alerts", response_model=List[Alert])
async def get_alerts():
    return alert_engine.alerts


@app.get("/api/summary")
async def get_summary():
    total = len(_state)
    online = sum(1 for d in _state if d.status.value == "ONLINE")
    offline = sum(1 for d in _state if d.status.value == "OFFLINE")
    degraded = sum(1 for d in _state if d.status.value == "DEGRADED")
    loops = sum(len(d.loops) for d in _state)
    cable = sum(len(d.cable_faults) for d in _state)
    avg_cpu = round(sum(d.cpu for d in _state) / total, 1) if total else 0
    return {
        "total": total, "online": online, "offline": offline,
        "degraded": degraded, "loops": loops, "cable_faults": cable,
        "avg_cpu": avg_cpu,
        "open_alerts": sum(1 for a in alert_engine.alerts if not a.acknowledged),
    }


# ----------------------------- CLI ------------------------------
class CliCommand(BaseModel):
    command: str


@app.post("/api/cli")
async def run_cli(cmd: CliCommand):
    return {"output": _dispatch_cli(cmd.command.strip())}


def _dispatch_cli(cmd: str) -> str:
    parts = cmd.split()
    if not parts:
        return ""
    head = parts[0].lower()

    if cmd == "show devices":
        rows = [f"{d.name:<22} {d.ip:<14} {d.status.value:<10} "
                f"CPU {d.cpu:>5}%  MEM {d.memory:>5}%  {d.ports_up}/{d.ports_total} ports up"
                for d in _state]
        return "\n".join(rows) or "no devices"

    if cmd.startswith("show device "):
        name = cmd[12:].strip().lower()
        dev = next((d for d in _state if d.name.lower() == name or d.id.lower() == name), None)
        if not dev:
            return f"device '{name}' not found. try: show devices"
        lines = [
            f"Name:     {dev.name}",
            f"Vendor:   {dev.vendor.value}",
            f"IP:       {dev.ip}",
            f"Status:   {dev.status.value}",
            f"CPU:      {dev.cpu}%",
            f"Memory:   {dev.memory}%",
            f"Uptime:   {dev.uptime_seconds // 3600}h {(dev.uptime_seconds % 3600) // 60}m",
            f"Ports:    {dev.ports_up}/{dev.ports_total} up",
        ]
        if dev.loops:
            lines.append(f"Loops:    {len(dev.loops)} active")
            for l in dev.loops:
                lines.append(f"          └─ {l.port}: {l.detail}")
        if dev.cable_faults:
            lines.append(f"Faults:   {len(dev.cable_faults)} active")
            for f in dev.cable_faults:
                lines.append(f"          └─ {f.port}: {f.detail}")
        return "\n".join(lines)

    if cmd == "show loops":
        out = [f"{d.name}: {l.port} — {l.detail}"
               for d in _state for l in d.loops]
        return "\n".join(out) or "no loops detected"

    if cmd == "show faults":
        out = [f"{d.name}: {f.port} — {f.detail}"
               for d in _state for f in d.cable_faults]
        return "\n".join(out) or "no cable faults"

    if cmd == "top":
        lines = [
            f"{'DEVICE':<22} {'STATUS':<10} {'CPU':>6} {'MEM':>6} {'LOOPS':>6} {'FAULTS':>7}",
            "-" * 65,
        ]
        sorted_devs = sorted(_state, key=lambda d: d.cpu, reverse=True)
        for d in sorted_devs:
            lines.append(
                f"{d.name:<22} {d.status.value:<10} {d.cpu:>5.1f}% {d.memory:>5.1f}% "
                f"{len(d.loops):>5}  {len(d.cable_faults):>6}"
            )
        return "\n".join(lines)

    if head == "ping" and len(parts) > 1:
        ip = parts[1]
        dev = next((d for d in _state if d.ip == ip), None)
        if dev and dev.status.value != "OFFLINE":
            return f"Reply from {ip}: time<1ms  ({dev.name})"
        return f"Request timed out: {ip} unreachable"

    if cmd == "show alerts":
        if not alert_engine.alerts:
            return "no alerts"
        lines = []
        for a in alert_engine.alerts[:20]:
            lines.append(f"[{a.severity.upper():<8}] {a.message}  ({a.created_at[:19]})")
        return "\n".join(lines)

    if cmd == "help":
        return (
            "commands:\n"
            "  show devices          — list all devices\n"
            "  show device <name>    — detailed view of one device\n"
            "  show loops            — active loop detections\n"
            "  show faults           — active cable/RJ45 faults\n"
            "  show alerts           — recent alert feed\n"
            "  top                   — devices ranked by CPU usage\n"
            "  ping <ip>             — test reachability\n"
            "  ask <question>        — ask the AI assistant\n"
            "  help                  — this message"
        )

    if head == "ask" and len(parts) > 1:
        query = " ".join(parts[1:])
        return _ask_ai(query)

    return f"unknown command: {cmd!r}  (try 'help')"


def _ask_ai(query: str) -> str:
    """Route a question to Claude with full network context."""
    if not CLAUDE_API_KEY:
        return "AI not configured. Set CLAUDE_API_KEY in server.py to enable."

    snapshot = json.dumps([{
        "name": d.name, "vendor": d.vendor.value, "ip": d.ip,
        "status": d.status.value, "cpu": d.cpu, "memory": d.memory,
        "loops": len(d.loops), "cable_faults": len(d.cable_faults),
    } for d in _state], indent=2)

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 500,
        "system": (
            "You are an expert network operations center AI. You have live "
            "telemetry data from monitored devices. Be concise and technical. "
            "Here is the current network state:\n" + snapshot
        ),
        "messages": [{"role": "user", "content": query}],
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"]
    except Exception as e:
        return f"AI error: {e}"


# ----------------------------- AI ASSIST --------------------------
class AiAssistRequest(BaseModel):
    messages: list
    network_context: Optional[str] = ""


@app.post("/api/ai-assist")
async def ai_assist(req: AiAssistRequest):
    if not CLAUDE_API_KEY:
        raise HTTPException(status_code=503, detail="AI not configured. Set CLAUDE_API_KEY in server.py.")

    system_prompt = (
        "You are an expert NOC AI assistant. You analyze live network telemetry "
        "and provide concise, technical recommendations. The operator will ask "
        "about device health, troubleshooting, and optimization.\n\n"
        "Current network state:\n" + req.network_context
    )

    api_messages = []
    for msg in req.messages:
        if msg.get("role") in ("user", "assistant"):
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    payload = json.dumps({
        "model": "claude-sonnet-4-6",
        "max_tokens": 800,
        "system": system_prompt,
        "messages": api_messages,
    }).encode()

    try:
        api_req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": CLAUDE_API_KEY,
                "anthropic-version": "2023-06-01",
            },
        )
        with urllib.request.urlopen(api_req, timeout=20) as resp:
            data = json.loads(resp.read())
            return {"response": data["content"][0]["text"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI error: {e}")


# --------------------------- WebSocket --------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    await ws.send_json({"type": "devices",
                        "data": [d.model_dump() for d in _state]})
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)