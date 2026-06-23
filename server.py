"""
AI-NOC Dashboard — Backend server (Phase 3).

Run:
    pip install fastapi "uvicorn[standard]"
    uvicorn server:app --reload --host 0.0.0.0 --port 8000

Then point your React frontend at http://localhost:8000.
Interactive API docs are auto-generated at http://localhost:8000/docs

Endpoints:
    GET  /api/devices      -> list of all devices (your existing 5s poll)
    GET  /api/devices/{id} -> one device
    GET  /api/alerts       -> recent alerts feed
    GET  /api/summary      -> KPI rollup for the Overview screen
    POST /api/cli          -> run a CLI command, get text back
    WS   /ws               -> live push of device state (no polling needed)
    GET  /api/health       -> liveness check
"""

import asyncio
import contextlib
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import Device, Alert
from collectors.simulator import SimulatorCollector
# from collectors.snmp_collector import SnmpCollector, SnmpDevice
from alerts import AlertEngine

# ---- SWAP DATA SOURCE HERE (one line to go to real devices) ----
collector = SimulatorCollector()
# collector = SnmpCollector(devices=[
#     SnmpDevice("core-sw-01", "Core-Switch-01", Vendor.CISCO, "10.0.0.1", "public"),
# ])

alert_engine = AlertEngine(
    cpu_threshold=85, mem_threshold=90,
    webhook_url=None,  # <-- paste a Slack/Discord webhook URL to enable notifications
)

POLL_INTERVAL = 5  # seconds — matches your frontend heartbeat

app = FastAPI(title="AI-NOC Dashboard API", version="1.0")

# CORS: allow your React dev server. Add your deployed origin for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- shared state, refreshed by the background poller ----
_state: List[Device] = []
_ws_clients: set[WebSocket] = set()


async def _poll_loop() -> None:
    """Single background task polls the collector; everyone reads _state."""
    global _state
    await collector.startup()
    while True:
        try:
            _state = await collector.collect()
            alert_engine.evaluate(_state)
            # push to any connected websocket clients
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
        rows = [f"{d.name:<20} {d.ip:<14} {d.status.value:<10} "
                f"CPU {d.cpu}%  {d.ports_up}/{d.ports_total} up"
                for d in _state]
        return "\n".join(rows) or "no devices"

    if cmd == "show loops":
        out = [f"{d.name}: {l.port} — {l.detail}"
               for d in _state for l in d.loops]
        return "\n".join(out) or "no loops detected"

    if cmd == "show faults":
        out = [f"{d.name}: {f.port} — {f.detail}"
               for d in _state for f in d.cable_faults]
        return "\n".join(out) or "no cable faults"

    if head == "ping" and len(parts) > 1:
        ip = parts[1]
        dev = next((d for d in _state if d.ip == ip), None)
        if dev and dev.status.value != "OFFLINE":
            return f"Reply from {ip}: time<1ms  ({dev.name})"
        return f"Request timed out: {ip} unreachable"

    if cmd == "help":
        return ("commands: show devices | show loops | show faults | "
                "ping <ip> | help")

    return f"unknown command: {cmd!r}  (try 'help')"


# --------------------------- WebSocket --------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.add(ws)
    # send current state immediately on connect
    await ws.send_json({"type": "devices",
                        "data": [d.model_dump() for d in _state]})
    try:
        while True:
            await ws.receive_text()  # keepalive / ignore client msgs
    except WebSocketDisconnect:
        _ws_clients.discard(ws)
