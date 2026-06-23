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
