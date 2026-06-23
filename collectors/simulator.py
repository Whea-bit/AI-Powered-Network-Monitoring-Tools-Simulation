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
