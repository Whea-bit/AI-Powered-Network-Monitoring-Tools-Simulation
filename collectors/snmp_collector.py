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
