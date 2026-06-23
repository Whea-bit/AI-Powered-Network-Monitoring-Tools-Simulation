#!/usr/bin/env bash
# AI-NOC backend installer -- run from inside ~/ai-noc/
set -e
echo "Creating backend files in $(pwd) ..."
mkdir -p collectors
touch collectors/__init__.py

cat > models.py << 'NOC_EOF'
"""
Data models for the AI-NOC Dashboard.

These Pydantic models define the EXACT JSON contract your React frontend
consumes. Any data source (simulator, SNMP, SSH, vendor API) must produce
a Device object that serializes to this shape. Keep this file as the single
source of truth — if the frontend and backend ever disagree, fix it here.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Status(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"  # reachable but a threshold is breached


class Vendor(str, Enum):
    CISCO = "Cisco"
    FORTIGATE = "FortiGate"
    ARUBA = "HPE Aruba"
    MERAKI = "Meraki"


class PortState(str, Enum):
    UP = "up"
    DOWN = "down"
    FAULT = "fault"  # physical / RJ45 / TDR fault


class Port(BaseModel):
    name: str                 # e.g. "Gi1/0/1"
    state: PortState
    utilization: float = 0.0  # percent, 0-100
    speed_mbps: int = 1000


class Fault(BaseModel):
    """A physical-layer or topology fault (loop, RJ45 termination, etc.)."""
    type: str                 # "loop" | "rj45" | "crc" | ...
    port: str
    detail: str
    detected_at: str


class Device(BaseModel):
    id: str
    name: str
    vendor: Vendor
    ip: str
    status: Status
    cpu: float = 0.0          # percent
    memory: float = 0.0       # percent
    uptime_seconds: int = 0
    ports: List[Port] = Field(default_factory=list)
    loops: List[Fault] = Field(default_factory=list)
    cable_faults: List[Fault] = Field(default_factory=list)
    last_polled: str = ""

    @property
    def ports_up(self) -> int:
        return sum(1 for p in self.ports if p.state == PortState.UP)

    @property
    def ports_total(self) -> int:
        return len(self.ports)


class Alert(BaseModel):
    id: str
    device_id: str
    device_name: str
    severity: str             # "critical" | "warning" | "info"
    message: str
    created_at: str
    acknowledged: bool = False


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
NOC_EOF

cat > alerts.py << 'NOC_EOF'
"""
Alert engine — detects state CHANGES and fires notifications.

Polling gives you a snapshot; this turns snapshots into events. It compares
the previous poll to the current one and emits alerts only on transitions
(edge-triggered), so you don't spam the same alert every 5 seconds.

Notification channels are pluggable. The webhook sender is included and
works with Slack/Discord/Teams incoming webhooks out of the box; email/SMS
are left as clearly-marked extension points.
"""

import uuid
from typing import Dict, List, Optional
from models import Device, Alert, Status, now_iso


class AlertEngine:
    def __init__(self, cpu_threshold: float = 85, mem_threshold: float = 90,
                 webhook_url: Optional[str] = None):
        self.cpu_threshold = cpu_threshold
        self.mem_threshold = mem_threshold
        self.webhook_url = webhook_url
        self._prev: Dict[str, Status] = {}
        self._prev_fault_counts: Dict[str, int] = {}
        self.alerts: List[Alert] = []  # ring buffer of recent alerts

    def _add(self, dev: Device, severity: str, message: str) -> None:
        alert = Alert(
            id=str(uuid.uuid4())[:8],
            device_id=dev.id, device_name=dev.name,
            severity=severity, message=message, created_at=now_iso(),
        )
        self.alerts.insert(0, alert)
        self.alerts = self.alerts[:100]  # keep last 100
        self._notify(alert)

    def evaluate(self, devices: List[Device]) -> None:
        for dev in devices:
            prev = self._prev.get(dev.id)

            # --- status transitions (edge-triggered) ---
            if prev is not None and prev != dev.status:
                if dev.status == Status.OFFLINE:
                    self._add(dev, "critical", f"{dev.name} went OFFLINE ({dev.ip})")
                elif prev == Status.OFFLINE and dev.status != Status.OFFLINE:
                    self._add(dev, "info", f"{dev.name} recovered — back ONLINE")
                elif dev.status == Status.DEGRADED:
                    self._add(dev, "warning",
                              f"{dev.name} DEGRADED — CPU {dev.cpu}% MEM {dev.memory}%")
            self._prev[dev.id] = dev.status

            # --- new physical faults ---
            fault_total = len(dev.loops) + len(dev.cable_faults)
            prev_faults = self._prev_fault_counts.get(dev.id, 0)
            if fault_total > prev_faults:
                if dev.loops:
                    self._add(dev, "critical",
                              f"LOOP detected on {dev.name}:{dev.loops[-1].port}")
                if dev.cable_faults:
                    cf = dev.cable_faults[-1]
                    self._add(dev, "warning",
                              f"Cable fault {dev.name}:{cf.port} — {cf.detail}")
            self._prev_fault_counts[dev.id] = fault_total

    def _notify(self, alert: Alert) -> None:
        """Fan out to configured channels. Failures here never break polling."""
        if self.webhook_url:
            try:
                import urllib.request, json
                payload = json.dumps({
                    "text": f"[{alert.severity.upper()}] {alert.message}"
                }).encode()
                req = urllib.request.Request(
                    self.webhook_url, data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=3)
            except Exception as e:
                print(f"[alert] webhook failed: {e}")
        # EXTENSION POINTS:
        #   email -> smtplib / SendGrid
        #   SMS   -> Twilio
        #   PagerDuty -> Events API v2
NOC_EOF

cat > server.py << 'NOC_EOF'
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
NOC_EOF

cat > requirements.txt << 'NOC_EOF'
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.0

# Uncomment when you move to real devices:
# pysnmp>=4.4
# netmiko>=4.0
# requests>=2.31      # for Meraki / FortiGate REST APIs
NOC_EOF

cat > collectors/base.py << 'NOC_EOF'
"""
Collector interface — the most important architectural piece.

A Collector is anything that can produce a list of Device objects. The API
layer never knows or cares whether the data came from a simulator or a real
SNMP poll. This is the seam that lets you develop against fakes today and
swap in real hardware later by changing ONE line in server.py.

To add real device support, subclass BaseCollector and implement collect().
See collectors/snmp_collector.py for a worked stub.
"""

from abc import ABC, abstractmethod
from typing import List
from models import Device


class BaseCollector(ABC):
    """All data sources implement this single method."""

    name: str = "base"

    @abstractmethod
    async def collect(self) -> List[Device]:
        """Return the current state of all monitored devices."""
        raise NotImplementedError

    async def startup(self) -> None:
        """Optional: open SSH/SNMP sessions, load config, etc."""
        pass

    async def shutdown(self) -> None:
        """Optional: clean up sessions on server stop."""
        pass
NOC_EOF

cat > collectors/simulator.py << 'NOC_EOF'
"""
Simulator collector — stateful, realistic fake telemetry.

Unlike a naive random generator, this keeps device state BETWEEN polls so
metrics drift smoothly and faults persist for a while before clearing. This
properly exercises your frontend's conditional logic: green/red borders,
DEGRADED states, loop badges, and cable-fault display all actually fire.

Behaviour:
  - CPU/memory random-walk within realistic bounds per vendor role
  - ~2% chance per poll a device flips OFFLINE, then recovers after a bit
  - ~3% chance a random port develops an RJ45/TDR fault
  - ~1.5% chance a loop is detected on an access switch, auto-clears later
"""

import random
from typing import Dict, List
from collectors.base import BaseCollector
from models import (
    Device, Port, Fault, Vendor, Status, PortState, now_iso,
)


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _walk(current: float, volatility: float = 4.0) -> float:
    return _clamp(current + random.uniform(-volatility, volatility))


class SimulatorCollector(BaseCollector):
    name = "simulator"

    def __init__(self) -> None:
        self._devices: Dict[str, Device] = {}
        self._offline_ttl: Dict[str, int] = {}   # polls remaining offline
        self._seed_devices()

    def _seed_devices(self) -> None:
        seeds = [
            ("core-sw-01", "Core-Switch-01", Vendor.CISCO, "10.0.0.1", 48),
            ("dist-fw-01", "Edge-FortiGate", Vendor.FORTIGATE, "10.0.0.2", 16),
            ("acc-ap-01", "Aruba-AP-Lobby", Vendor.ARUBA, "10.0.1.10", 4),
            ("acc-ap-02", "Meraki-AP-Hall", Vendor.MERAKI, "10.0.1.11", 4),
            ("acc-sw-02", "Access-Switch-02", Vendor.CISCO, "10.0.0.5", 24),
        ]
        for did, name, vendor, ip, nports in seeds:
            ports = [
                Port(
                    name=f"Port{ i +1}",
                    state=PortState.UP if random.random() > 0.25 else PortState.DOWN,
                    utilization=round(random.uniform(2, 55), 1),
                )
                for i in range(nports)
            ]
            self._devices[did] = Device(
                id=did, name=name, vendor=vendor, ip=ip,
                status=Status.ONLINE,
                cpu=round(random.uniform(10, 40), 1),
                memory=round(random.uniform(30, 60), 1),
                uptime_seconds=random.randint(3600, 5_000_000),
                ports=ports,
                last_polled=now_iso(),
            )

    async def collect(self) -> List[Device]:
        for did, dev in self._devices.items():
            # --- handle offline recovery ---
            if dev.status == Status.OFFLINE:
                self._offline_ttl[did] -= 1
                if self._offline_ttl[did] <= 0:
                    dev.status = Status.ONLINE
                else:
                    dev.last_polled = now_iso()
                    continue  # offline device reports nothing else

            # --- random offline event ---
            if random.random() < 0.02:
                dev.status = Status.OFFLINE
                self._offline_ttl[did] = random.randint(2, 5)
                dev.last_polled = now_iso()
                continue

            # --- drift metrics ---
            dev.cpu = round(_walk(dev.cpu, 5), 1)
            dev.memory = round(_walk(dev.memory, 2), 1)
            dev.uptime_seconds += 5
            for p in dev.ports:
                if p.state == PortState.UP:
                    p.utilization = round(_walk(p.utilization, 6), 1)

            # --- DEGRADED if a threshold is breached ---
            dev.status = (
                Status.DEGRADED if (dev.cpu > 85 or dev.memory > 90)
                else Status.ONLINE
            )

            # --- RJ45 / cable fault injection ---
            if random.random() < 0.03 and dev.ports:
                p = random.choice(dev.ports)
                if p.state != PortState.FAULT:
                    p.state = PortState.FAULT
                    dev.cable_faults.append(Fault(
                        type="rj45",
                        port=p.name,
                        detail="TDR: impedance mismatch ~12m (open pair 4,5)",
                        detected_at=now_iso(),
                    ))
            # clear an old cable fault occasionally
            if dev.cable_faults and random.random() < 0.15:
                cleared = dev.cable_faults.pop(0)
                for p in dev.ports:
                    if p.name == cleared.port:
                        p.state = PortState.UP

            # --- loop detection (access switches only) ---
            if dev.vendor == Vendor.CISCO and random.random() < 0.015:
                if not dev.loops:
                    dev.loops.append(Fault(
                        type="loop",
                        port=random.choice(dev.ports).name if dev.ports else "Port1",
                        detail="STP topology change: BPDU loop suspected",
                        detected_at=now_iso(),
                    ))
            if dev.loops and random.random() < 0.2:
                dev.loops.pop(0)

            dev.last_polled = now_iso()

        return list(self._devices.values())
NOC_EOF

cat > collectors/snmp_collector.py << 'NOC_EOF'
"""
SNMP collector — the path from simulation to REAL devices.

This is a STUB with the real OIDs and structure in place, so you can see
exactly how production polling slots into the same interface. To activate:

    pip install pysnmp
    # then in server.py:  collector = SnmpCollector(devices=[...])

WHY SNMP first: it's read-only, non-disruptive, and supported by Cisco,
FortiGate, Aruba, and Meraki (Meraki also has a cloud REST API which is
usually better — see note at bottom). Loop and RJ45/TDR detection need SSH
or vendor APIs on top of this; SNMP alone gives you status + utilization.
"""

from typing import List, Dict
from collectors.base import BaseCollector
from models import Device, Vendor, Status, now_iso

# Standard IF-MIB / HOST-RESOURCES OIDs you'll poll:
OIDS = {
    "sysUpTime":      "1.3.6.1.2.1.1.3.0",
    "ifOperStatus":   "1.3.6.1.2.1.2.2.1.8",        # per-port up/down
    "ifHCInOctets":   "1.3.6.1.2.1.31.1.1.1.6",     # 64-bit in counter
    "ifHCOutOctets":  "1.3.6.1.2.1.31.1.1.1.10",    # 64-bit out counter
    "ifSpeed":        "1.3.6.1.2.1.2.2.1.5",
    # CPU/memory OIDs are vendor-specific (Cisco CISCO-PROCESS-MIB, etc.)
    "cisco_cpu":      "1.3.6.1.4.1.9.9.109.1.1.1.1.7.1",
}


class SnmpDevice:
    def __init__(self, id: str, name: str, vendor: Vendor, ip: str,
                 community: str = "public"):
        self.id, self.name, self.vendor, self.ip = id, name, vendor, ip
        self.community = community
        self._last_counters: Dict[str, int] = {}  # for utilization deltas


class SnmpCollector(BaseCollector):
    name = "snmp"

    def __init__(self, devices: List[SnmpDevice], poll_interval: int = 5):
        self.devices = devices
        self.poll_interval = poll_interval

    async def collect(self) -> List[Device]:
        results: List[Device] = []
        for d in self.devices:
            try:
                # results.append(await self._poll_one(d))
                raise NotImplementedError(
                    "Install pysnmp and implement _poll_one(). The OIDs and "
                    "structure are already laid out above."
                )
            except Exception:
                # Unreachable device => OFFLINE, never crash the poll loop.
                results.append(Device(
                    id=d.id, name=d.name, vendor=d.vendor, ip=d.ip,
                    status=Status.OFFLINE, last_polled=now_iso(),
                ))
        return results

    # async def _poll_one(self, d: SnmpDevice) -> Device:
    #     1. GET sysUpTime -> if timeout, OFFLINE
    #     2. WALK ifOperStatus -> build Port list
    #     3. GET ifHCIn/OutOctets -> compute (delta_bytes*8)/(interval*speed)
    #        = utilization %, using self._last_counters
    #     4. GET vendor CPU/mem OID
    #     5. return Device(...)

# NOTE on Meraki: prefer the Meraki Dashboard API (cloud REST) over SNMP —
# GET /organizations/{id}/devices/statuses and /networks/{id}/clients.
# FortiGate: prefer its REST API (/api/v2/monitor/...) for richer data.
# Loop + TDR cable diagnostics require SSH (Netmiko) — see collectors/ssh.py
# as your next extension.
NOC_EOF

echo ""
echo "Done. Files created:"
ls -1 *.py collectors/*.py
echo ""
echo "Next steps:"
echo "  pip install -r requirements.txt"
echo "  uvicorn server:app --reload --host 0.0.0.0 --port 8000"