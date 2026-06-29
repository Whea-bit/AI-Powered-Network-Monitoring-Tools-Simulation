"""AI-NOC Dashboard — Backend server with Gemini AI + real ICMP ping.
Run: uvicorn server:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import contextlib
import json
import urllib.request
import urllib.error
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import Device, Alert
from collectors.simulator import SimulatorCollector
from alerts import AlertEngine
from collectors.icmp_collector import ping_host_async, format_ping_output

# ----------------------------- Config -----------------------------
collector = SimulatorCollector()

alert_engine = AlertEngine(
    cpu_threshold=85,
    mem_threshold=90,
    webhook_url=None,
)

POLL_INTERVAL = 5

# --- PASTE YOUR NEW GEMINI API KEY HERE AFTER REGENERATING IT ---
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-1.5-flash"  # more generous free quota than 2.0-flash

# ----------------------------- App setup -------------------------
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

# In-memory settings store (persists while server runs)
_settings = {
    "cpu_threshold": 85,
    "mem_threshold": 90,
    "email_enabled": False,
    "email_address": "",
}

# ----------------------------- Gemini AI -------------------------
def _call_gemini(system_prompt: str, messages: list) -> str:
    """Call Google Gemini API and return the text response."""
    if not GEMINI_API_KEY:
        return "AI not configured. Paste your Gemini API key into GEMINI_API_KEY in server.py."

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    # Convert messages to Gemini format
    contents = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        content = str(msg.get("content", "")).strip()
        if content:
            contents.append({
                "role": role,
                "parts": [{"text": content}]
            })

    # Gemini requires conversation to start with a user message
    if contents and contents[0]["role"] == "model":
        contents.insert(0, {
            "role": "user",
            "parts": [{"text": "Initialize network analysis."}]
        })

    if not contents:
        return "Error: no message content to send."

    payload = json.dumps({
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": 800,
            "temperature": 0.7
        }
    }).encode()

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return data["candidates"][0]["content"]["parts"][0]["text"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return f"Gemini API error ({e.code}): {error_body[:300]}"
    except Exception as e:
        return f"AI error: {e}"


def _get_network_snapshot() -> str:
    """Serialize current device state for AI context."""
    return json.dumps([{
        "name": d.name,
        "vendor": d.vendor.value,
        "ip": d.ip,
        "status": d.status.value,
        "cpu": d.cpu,
        "memory": d.memory,
        "loops": len(d.loops),
        "cable_faults": len(d.cable_faults),
        "ports_up": d.ports_up,
        "ports_total": d.ports_total,
    } for d in _state], indent=2)


# ----------------------------- Poll loop -------------------------
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


# ----------------------------- REST endpoints --------------------
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "source": collector.name,
        "devices": len(_state),
        "ai": "configured" if GEMINI_API_KEY else "not configured",
    }


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
        "total": total,
        "online": online,
        "offline": offline,
        "degraded": degraded,
        "loops": loops,
        "cable_faults": cable,
        "avg_cpu": avg_cpu,
        "open_alerts": sum(1 for a in alert_engine.alerts if not a.acknowledged),
    }


@app.get("/api/settings")
async def get_settings():
    return _settings


@app.post("/api/settings")
async def save_settings(req: dict):
    global _settings
    # Update stored settings
    _settings.update(req)

    # Apply thresholds to the live alert engine immediately
    if "cpu_threshold" in req:
        alert_engine.cpu_threshold = float(req["cpu_threshold"])
    if "mem_threshold" in req:
        alert_engine.mem_threshold = float(req["mem_threshold"])

    return {"status": "ok", "applied": _settings}


# ----------------------------- CLI ------------------------------
class CliCommand(BaseModel):
    command: str


@app.post("/api/cli")
async def run_cli(cmd: CliCommand):
    return {"output": await _dispatch_cli(cmd.command.strip())}


async def _dispatch_cli(cmd: str) -> str:
    parts = cmd.split()
    if not parts:
        return ""
    head = parts[0].lower()

    # show devices
    if cmd == "show devices":
        rows = [
            f"{d.name:<22} {d.ip:<14} {d.status.value:<10} "
            f"CPU {d.cpu:>5}%  MEM {d.memory:>5}%  {d.ports_up}/{d.ports_total} ports up"
            for d in _state
        ]
        return "\n".join(rows) or "no devices"

    # show device <name>
    if cmd.startswith("show device "):
        name = cmd[12:].strip().lower()
        dev = next(
            (d for d in _state if d.name.lower() == name or d.id.lower() == name),
            None
        )
        if not dev:
            return f"device '{name}' not found. try: show devices"
        lines = [
            f"Name:     {dev.name}",
            f"Vendor:   {dev.vendor.value}",
            f"IP:       {dev.ip}",
            f"Status:   {dev.status.value}",
            f"CPU:      {dev.cpu}%",
            f"Memory:   {dev.memory}%",
            f"Uptime:   {dev.uptime_seconds // 3600}h "
            f"{(dev.uptime_seconds % 3600) // 60}m",
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

    # show loops
    if cmd == "show loops":
        out = [f"{d.name}: {l.port} — {l.detail}"
               for d in _state for l in d.loops]
        return "\n".join(out) or "no loops detected"

    # show faults
    if cmd == "show faults":
        out = [f"{d.name}: {f.port} — {f.detail}"
               for d in _state for f in d.cable_faults]
        return "\n".join(out) or "no cable faults"

    # show alerts
    if cmd == "show alerts":
        if not alert_engine.alerts:
            return "no alerts recorded yet"
        lines = []
        for a in alert_engine.alerts[:20]:
            lines.append(
                f"[{a.severity.upper():<8}] {a.message}  ({a.created_at[:19]})"
            )
        return "\n".join(lines)

    # top — devices ranked by CPU
    if cmd == "top":
        lines = [
            f"{'DEVICE':<22} {'STATUS':<10} {'CPU':>6} {'MEM':>6} "
            f"{'LOOPS':>6} {'FAULTS':>7}",
            "-" * 65,
        ]
        for d in sorted(_state, key=lambda d: d.cpu, reverse=True):
            lines.append(
                f"{d.name:<22} {d.status.value:<10} {d.cpu:>5.1f}% "
                f"{d.memory:>5.1f}% {len(d.loops):>5}  {len(d.cable_faults):>6}"
            )
        return "\n".join(lines)

    # ping — REAL ICMP
    if head == "ping" and len(parts) > 1:
        target = parts[1]
        # allow pinging by device name as well as IP
        if not target[0].isdigit():
            dev = next(
                (d for d in _state if d.name.lower() == target.lower()),
                None
            )
            if dev:
                target = dev.ip
            else:
                return f"unknown host: {target!r}  (use an IP or a device name)"
        result = await ping_host_async(target, count=3, timeout=1.0)
        dev = next((d for d in _state if d.ip == target), None)
        name_hint = f"  [{dev.name}]" if dev else ""
        return format_ping_output(result) + name_hint

    # ask — route to Gemini AI
    if head == "ask" and len(parts) > 1:
        query = " ".join(parts[1:])
        system = (
            "You are an expert network operations center AI. "
            "Be concise and technical. "
            "Here is the current network state:\n" + _get_network_snapshot()
        )
        return _call_gemini(system, [{"role": "user", "content": query}])

    # help
    if cmd == "help":
        return (
            "commands:\n"
            "  show devices          — list all devices\n"
            "  show device <name>    — detailed view of one device\n"
            "  show loops            — active loop detections\n"
            "  show faults           — active cable/RJ45 faults\n"
            "  show alerts           — recent alert feed\n"
            "  top                   — devices ranked by CPU usage\n"
            "  ping <ip or name>     — real ICMP ping test\n"
            "  ask <question>        — ask the Gemini AI assistant\n"
            "  help                  — this message"
        )

    return f"unknown command: {cmd!r}  (try 'help')"


# ----------------------------- AI Assist -------------------------
@app.post("/api/ai-assist")
async def ai_assist(req: dict):
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="AI not configured. Paste your Gemini key into GEMINI_API_KEY in server.py."
        )

    network_context = req.get("network_context", "")
    system_prompt = (
        "You are an expert NOC AI assistant. Provide concise, technical "
        "troubleshooting advice based on live device telemetry.\n"
        "Current network state:\n" + str(network_context)
    )

    # Build message list — handle both formats the frontend might send
    api_messages = []
    if "messages" in req and isinstance(req["messages"], list):
        for msg in req["messages"]:
            if isinstance(msg, dict):
                role = "user" if msg.get("role") == "user" else "model"
                content = str(msg.get("content", "")).strip()
                if content:
                    api_messages.append({"role": role, "content": content})
    elif "message" in req:
        content = str(req["message"]).strip()
        if content:
            api_messages.append({"role": "user", "content": content})

    if not api_messages:
        return {"response": "Error: received empty message."}

    result = _call_gemini(system_prompt, api_messages)

    if result.startswith("Gemini API error") or result.startswith("AI error"):
        raise HTTPException(status_code=500, detail=result)

    return {"response": result}


# ----------------------------- WebSocket ------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    await ws.send_json({
        "type": "devices",
        "data": [d.model_dump() for d in _state]
    })
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.discard(ws)