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
