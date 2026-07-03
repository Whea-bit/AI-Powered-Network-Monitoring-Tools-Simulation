"""Alert engine — edge-triggered notifications saved to PostgreSQL + email alerts."""

import uuid
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional

from models import Device, Alert, Status, now_iso


class AlertEngine:
    def __init__(self, cpu_threshold: float = 85, mem_threshold: float = 90,
                 email_enabled: bool = False,
                 email_address: str = ""):
        self.cpu_threshold = cpu_threshold
        self.mem_threshold = mem_threshold
        self.email_enabled = email_enabled
        self.email_address = email_address
        self._prev: Dict[str, Status] = {}
        self._prev_fault_counts: Dict[str, int] = {}
        self._initialized = False
        self.alerts: List[Alert] = []

    def _add(self, dev: Device, severity: str, message: str) -> None:
        alert = Alert(
            id=str(uuid.uuid4())[:8],
            device_id=dev.id, device_name=dev.name,
            severity=severity, message=message, created_at=now_iso(),
        )
        self.alerts.insert(0, alert)
        self.alerts = self.alerts[:100]

        # Save to PostgreSQL
        try:
            from database import save_alert
            save_alert({
                "id": alert.id,
                "device_id": alert.device_id,
                "device_name": alert.device_name,
                "severity": alert.severity,
                "message": alert.message,
                "acknowledged": alert.acknowledged,
            })
        except Exception as e:
            print(f"[db] save_alert error: {e}")

        # Send email in background
        self._notify(alert)

    def evaluate(self, devices: List[Device]) -> None:
        for dev in devices:
            prev = self._prev.get(dev.id)

            if self._initialized and prev is not None and prev != dev.status:
                if dev.status == Status.OFFLINE:
                    self._add(dev, "critical",
                              f"{dev.name} went OFFLINE ({dev.ip})")
                elif prev == Status.OFFLINE and dev.status != Status.OFFLINE:
                    self._add(dev, "info",
                              f"{dev.name} recovered — back ONLINE")
                elif dev.status == Status.DEGRADED:
                    self._add(dev, "warning",
                              f"{dev.name} DEGRADED — CPU {dev.cpu}% MEM {dev.memory}%")
            self._prev[dev.id] = dev.status

            fault_total = len(dev.loops) + len(dev.cable_faults)
            prev_faults = self._prev_fault_counts.get(dev.id, 0)
            if self._initialized and fault_total > prev_faults:
                if dev.loops:
                    self._add(dev, "critical",
                              f"LOOP detected on {dev.name}:{dev.loops[-1].port}")
                if dev.cable_faults:
                    cf = dev.cable_faults[-1]
                    self._add(dev, "warning",
                              f"Cable fault {dev.name}:{cf.port} — {cf.detail}")
            self._prev_fault_counts[dev.id] = fault_total

        self._initialized = True

    def _send_email(self, alert: Alert) -> None:
        """Send alert email in background thread."""
        try:
            from server import SMTP_SENDER_EMAIL, SMTP_APP_PASSWORD

            if not SMTP_SENDER_EMAIL or SMTP_SENDER_EMAIL == "your.gmail@gmail.com":
                print("[email] SMTP not configured in server.py")
                return
            if not self.email_address:
                print("[email] No recipient address set")
                return

            color = '#f87171' if alert.severity == 'critical' else '#fbbf24'
            msg = MIMEMultipart()
            msg["From"] = SMTP_SENDER_EMAIL
            msg["To"] = self.email_address
            msg["Subject"] = f"[AI-NOC] {alert.severity.upper()}: {alert.device_name}"
            msg.attach(MIMEText(f"""
            <html>
            <body style="font-family:sans-serif;background:#111827;color:#f3f4f6;padding:2rem;">
                <h2 style="color:{color}">AI-NOC Alert — {alert.severity.upper()}</h2>
                <table style="border-collapse:collapse;width:100%;max-width:500px;">
                    <tr><td style="padding:0.5rem;color:#9ca3af;">Device</td>
                        <td style="padding:0.5rem;">{alert.device_name}</td></tr>
                    <tr style="background:rgba(255,255,255,0.03);">
                        <td style="padding:0.5rem;color:#9ca3af;">Message</td>
                        <td style="padding:0.5rem;">{alert.message}</td></tr>
                    <tr><td style="padding:0.5rem;color:#9ca3af;">Severity</td>
                        <td style="padding:0.5rem;color:{color};">{alert.severity.upper()}</td></tr>
                    <tr style="background:rgba(255,255,255,0.03);">
                        <td style="padding:0.5rem;color:#9ca3af;">Time</td>
                        <td style="padding:0.5rem;">{alert.created_at}</td></tr>
                </table>
                <p style="color:#6b7280;font-size:0.75rem;margin-top:2rem;
                          border-top:1px solid #374151;padding-top:1rem;">
                    Sent by AI-NOC Dashboard • Network Operations Center
                </p>
            </body>
            </html>
            """, "html"))

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SMTP_SENDER_EMAIL, SMTP_APP_PASSWORD)
                server.send_message(msg)
            print(f"[email] sent to {self.email_address}: {alert.message}")

        except smtplib.SMTPAuthenticationError:
            print("[email] Auth failed — check SMTP_APP_PASSWORD in server.py")
        except smtplib.SMTPConnectError:
            print("[email] Port 465 blocked on this network")
        except Exception as e:
            print(f"[email] failed: {e}")

    def _notify(self, alert: Alert) -> None:
        """Fire email in background thread — never blocks the poll loop."""
        if not self.email_enabled or not self.email_address:
            return
        threading.Thread(
            target=self._send_email,
            args=(alert,),
            daemon=True
        ).start()