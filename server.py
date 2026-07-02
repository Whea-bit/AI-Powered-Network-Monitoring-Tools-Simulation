"""AI-NOC Dashboard — Backend with PostgreSQL, Gemini AI, ICMP ping, Email notifications.
Run: uvicorn server:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import contextlib
import json
import smtplib
import urllib.request
import urllib.error
import functools
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import Device, Alert
from collectors.simulator import SimulatorCollector
from alerts import AlertEngine
from collectors.icmp_collector import ping_host_async, format_ping_output
from database import (
    init_db, save_alert, get_alerts, save_setting,
    get_all_settings, save_ping, get_ping_history, get_uptime_percentage
)

# ----------------------------- Helper ----------------------------
async def _db_call(func, *args, **kwargs):
    """Push synchronous DB calls to a background thread."""
    loop = asyncio.get_running_loop()
    pfunc = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, pfunc)

# ----------------------------- Config ----------------------------
collector = SimulatorCollector()
POLL_INTERVAL = 5

# --- GEMINI API KEY ---
GEMINI_API_KEY = ""
GEMINI_MODEL = "gemini-1.5-flash"

# --- EMAIL CONFIG (Gmail SMTP) ---
# Step 1: Enable 2-Step Verification on your Gmail account
# Step 2: Go to myaccount.google.com → Security → App passwords
# Step 3: Generate a new App Password for "Mail"
# Step 4: Paste the 16-character password below (with spaces removed)
SMTP_SENDER_EMAIL = "your.gmail@gmail.com"   # <-- your Gmail address
SMTP_APP_PASSWORD  = "xxxx xxxx xxxx xxxx"   # <-- your 16-char App Password

# ----------------------------- App Setup -------------------------
app = FastAPI(title="AI-NOC Dashboard API", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://10.5.50.45:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_state: List[Device] = []
_ws_clients: set = set()

_settings = {
    "cpu_threshold": 85,
    "mem_threshold": 90,
    "email_enabled": False,
    "email_address": "",
}

alert_engine = AlertEngine(
    cpu_threshold=85,
    mem_threshold=90,
    email_enabled=False,
    email_address="",
)


async def _load_settings_from_db():
    """Load persisted settings from PostgreSQL on startup."""
    global _settings
    try:
        db_settings = await _db_call(get_all_settings)
        if db_settings:
            if "cpu_threshold" in db_settings:
                _settings["cpu_threshold"] = float(db_settings["cpu_threshold"])
            if "mem_threshold" in db_settings:
                _settings["mem_threshold"] = float(db_settings["mem_threshold"])
            if "email_enabled" in db_settings:
                _settings["email_enabled"] = db_settings["email_enabled"] in ["True", "true"]
            if "email_address" in db_settings:
                _settings["email_address"] = db_settings["email_address"]
            print(f"[db] Settings loaded: {_settings}")
    except Exception as e:
        print(f"[db] Could not load settings: {e}")


# ----------------------------- Email Helper ----------------------
def send_email(to_address: str, subject: str, html_body: str) -> bool:
    """Send an email via Gmail SMTP. Returns True if successful."""
    if not SMTP_SENDER_EMAIL or SMTP_SENDER_EMAIL == "your.gmail@gmail.com":
        print("[email] SMTP credentials not configured in server.py")
        return False
    if not SMTP_APP_PASSWORD or SMTP_APP_PASSWORD == "xxxx xxxx xxxx xxxx":
        print("[email] SMTP App Password not configured in server.py")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_SENDER_EMAIL
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SMTP_SENDER_EMAIL, SMTP_APP_PASSWORD)
            server.send_message(msg)
        print(f"[email] sent to {to_address}: {subject}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[email] Authentication failed — check SMTP_APP_PASSWORD in server.py")
        return False
    except smtplib.SMTPConnectError:
        print("[email] Could not connect to Gmail — port 465 may be blocked on this network")
        return False
    except Exception as e:
        print(f"[email] failed: {e}")
        return False


# ----------------------------- Gemini AI -------------------------
def _call_gemini(system_prompt: str, messages: list) -> str:
    if not GEMINI_API_KEY:
        return "AI not configured. Paste your Gemini API key into GEMINI_API_KEY in server.py."

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )

    contents = []
    for msg in messages:
        role = "user" if msg.get("role") == "user" else "model"
        content = str(msg.get("content", "")).strip()
        if content:
            contents.append({"role": role, "parts": [{"text": content}]})

    if contents and contents[0]["role"] == "model":
        contents.insert(0, {
            "role": "user",
            "parts": [{"text": "Initialize network analysis."}]
        })

    if not contents:
        return "Error: no message content to send."

    payload = json.dumps({
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 800, "temperature": 0.7}
    }).encode()

    try:
        req = urllib.request.Request(
            url, data=payload,
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
    return json.dumps([{
        "name": d.name, "vendor": d.vendor.value, "ip": d.ip,
        "status": d.status.value, "cpu": d.cpu, "memory": d.memory,
        "loops": len(d.loops), "cable_faults": len(d.cable_faults),
        "ports_up": d.ports_up, "ports_total": d.ports_total,
    } for d in _state], indent=2)


# ----------------------------- Poll Loop -------------------------
async def _poll_loop() -> None:
    global _state
    await collector.startup()
    loop = asyncio.get_running_loop()
    while True:
        try:
            _state = await collector.collect()
            await loop.run_in_executor(None, alert_engine.evaluate, _state)
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
    await _db_call(init_db)
    await _load_settings_from_db()
    alert_engine.cpu_threshold = float(_settings["cpu_threshold"])
    alert_engine.mem_threshold = float(_settings["mem_threshold"])
    alert_engine.email_enabled = _settings["email_enabled"]
    alert_engine.email_address = _settings["email_address"]
    app.state.poller = asyncio.create_task(_poll_loop())
    print("[startup] AI-NOC Dashboard ready.")


@app.on_event("shutdown")
async def _shutdown() -> None:
    app.state.poller.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await app.state.poller
    await collector.shutdown()


# ----------------------------- REST Endpoints --------------------
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "source": collector.name,
        "devices": len(_state),
        "ai": "configured" if GEMINI_API_KEY else "not configured",
        "email": "configured" if SMTP_SENDER_EMAIL != "your.gmail@gmail.com" else "not configured",
        "database": "postgresql",
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


@app.get("/api/alerts")
async def get_alerts_endpoint():
    return await _db_call(get_alerts, limit=100)


@app.get("/api/summary")
async def get_summary():
    total = len(_state)
    online = sum(1 for d in _state if d.status.value == "ONLINE")
    offline = sum(1 for d in _state if d.status.value == "OFFLINE")
    degraded = sum(1 for d in _state if d.status.value == "DEGRADED")
    loops = sum(len(d.loops) for d in _state)
    cable = sum(len(d.cable_faults) for d in _state)
    avg_cpu = round(sum(d.cpu for d in _state) / total, 1) if total else 0
    db_alerts = await _db_call(get_alerts, limit=100)
    open_alerts = sum(1 for a in db_alerts if not a.get("acknowledged"))
    return {
        "total": total, "online": online, "offline": offline,
        "degraded": degraded, "loops": loops, "cable_faults": cable,
        "avg_cpu": avg_cpu, "open_alerts": open_alerts,
    }


@app.get("/api/ping/{ip}")
async def ping_endpoint(ip: str):
    result = await ping_host_async(ip, count=3, timeout=1.0)
    dev = next((d for d in _state if d.ip == ip), None)
    device_name = dev.name if dev else ip
    await _db_call(
        save_ping, ip=ip, device_name=device_name,
        alive=result["alive"], avg_rtt=result.get("avg_rtt"),
        packet_loss=result.get("packet_loss"),
    )
    return result


@app.get("/api/ping-history/{ip}")
async def ping_history_endpoint(ip: str):
    history = await _db_call(get_ping_history, ip, limit=50)
    uptime = await _db_call(get_uptime_percentage, ip)
    return {"ip": ip, "uptime_percent": uptime, "history": history}


@app.get("/api/settings")
async def get_settings():
    return _settings


@app.post("/api/settings")
async def save_settings_endpoint(req: dict):
    global _settings
    _settings.update(req)

    if "cpu_threshold" in req:
        alert_engine.cpu_threshold = float(req["cpu_threshold"])
    if "mem_threshold" in req:
        alert_engine.mem_threshold = float(req["mem_threshold"])
    if "email_enabled" in req:
        alert_engine.email_enabled = req["email_enabled"] in [True, "True", "true"]
    if "email_address" in req:
        alert_engine.email_address = req["email_address"]

    for key, value in req.items():
        await _db_call(save_setting, key, str(value))

    return {"status": "ok", "applied": _settings}


@app.post("/api/test-email")
async def test_email(req: dict):
    """Send a test email to verify SMTP is working."""
    to_address = req.get("email", "")
    if not to_address:
        raise HTTPException(status_code=400, detail="No email address provided.")

    html_body = """
    <html>
    <body style="font-family:sans-serif;background:#111827;color:#f3f4f6;padding:2rem;">
        <h2 style="color:#4ade80">✓ AI-NOC Email Test Successful</h2>
        <p>Your email notification system is configured and working correctly.</p>
        <p>You will receive alerts like this when:</p>
        <ul>
            <li>A device goes <strong style="color:#f87171">OFFLINE</strong></li>
            <li>A device becomes <strong style="color:#fbbf24">DEGRADED</strong></li>
            <li>A loop or cable fault is detected</li>
            <li>A device recovers back ONLINE</li>
        </ul>
        <p style="color:#9ca3af;font-size:0.8rem;margin-top:2rem;
                  border-top:1px solid #374151;padding-top:1rem;">
            Sent by AI-NOC Dashboard • Network Operations Center
        </p>
    </body>
    </html>
    """

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None, send_email, to_address,
        "[AI-NOC] Test Notification ✓", html_body
    )

    if success:
        return {"status": "sent", "to": to_address}
    else:
        raise HTTPException(
            status_code=500,
            detail=(
                "Email failed. Check: "
                "1) SMTP_SENDER_EMAIL and SMTP_APP_PASSWORD in server.py, "
                "2) Gmail App Password is correct, "
                "3) Port 465 is not blocked on your network."
            )
        )


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

    if cmd == "show devices":
        rows = [
            f"{d.name:<22} {d.ip:<14} {d.status.value:<10} "
            f"CPU {d.cpu:>5}%  MEM {d.memory:>5}%  {d.ports_up}/{d.ports_total} ports up"
            for d in _state
        ]
        return "\n".join(rows) or "no devices"

    if cmd.startswith("show device "):
        name = cmd[12:].strip().lower()
        dev = next(
            (d for d in _state if d.name.lower() == name or d.id.lower() == name),
            None
        )
        if not dev:
            return f"device '{name}' not found. try: show devices"
        uptime_pct = await _db_call(get_uptime_percentage, dev.ip)
        lines = [
            f"Name:     {dev.name}",
            f"Vendor:   {dev.vendor.value}",
            f"IP:       {dev.ip}",
            f"Status:   {dev.status.value}",
            f"CPU:      {dev.cpu}%",
            f"Memory:   {dev.memory}%",
            f"Uptime:   {dev.uptime_seconds // 3600}h "
            f"{(dev.uptime_seconds % 3600) // 60}m",
            f"DB Uptime:{uptime_pct}% (from ping history)",
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

    if cmd == "show alerts":
        db_alerts = await _db_call(get_alerts, limit=20)
        if not db_alerts:
            return "no alerts recorded yet"
        lines = []
        for a in db_alerts:
            lines.append(
                f"[{a['severity'].upper():<8}] {a['message']}  "
                f"({a['created_at'][:19]})"
            )
        return "\n".join(lines)

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

    if head == "ping" and len(parts) > 1:
        target = parts[1]
        if not target[0].isdigit():
            dev = next(
                (d for d in _state if d.name.lower() == target.lower()),
                None
            )
            if dev:
                target = dev.ip
            else:
                return f"unknown host: {target!r}  (use an IP or device name)"
        result = await ping_host_async(target, count=3, timeout=1.0)
        dev = next((d for d in _state if d.ip == target), None)
        device_name = dev.name if dev else target
        await _db_call(
            save_ping, ip=target, device_name=device_name,
            alive=result["alive"], avg_rtt=result.get("avg_rtt"),
            packet_loss=result.get("packet_loss"),
        )
        name_hint = f"  [{device_name}]" if dev else ""
        return format_ping_output(result) + name_hint

    if head == "uptime" and len(parts) > 1:
        target = parts[1]
        dev = next(
            (d for d in _state if d.name.lower() == target.lower() or d.ip == target),
            None
        )
        ip = dev.ip if dev else target
        name = dev.name if dev else target
        uptime = await _db_call(get_uptime_percentage, ip)
        history = await _db_call(get_ping_history, ip, limit=10)
        lines = [f"Uptime for {name} ({ip}): {uptime}%"]
        if history:
            lines.append("Last 10 checks:")
            for h in history:
                status = "✓" if h["alive"] else "✗"
                rtt = f"{h['avg_rtt']}ms" if h["avg_rtt"] else "N/A"
                lines.append(f"  {status} {h['checked_at'][:19]}  RTT: {rtt}")
        return "\n".join(lines)

    if head == "ask" and len(parts) > 1:
        query = " ".join(parts[1:])
        system = (
            "You are an expert network operations center AI. "
            "Be concise and technical. "
            "Here is the current network state:\n" + _get_network_snapshot()
        )
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, _call_gemini, system, [{"role": "user", "content": query}]
        )

    if cmd == "help":
        return (
            "commands:\n"
            "  show devices          — list all devices\n"
            "  show device <name>    — detailed view + DB uptime\n"
            "  show loops            — active loop detections\n"
            "  show faults           — active cable/RJ45 faults\n"
            "  show alerts           — persistent alert history (DB)\n"
            "  top                   — devices ranked by CPU usage\n"
            "  ping <ip or name>     — real ICMP ping (saved to DB)\n"
            "  uptime <ip or name>   — uptime % from ping history\n"
            "  ask <question>        — ask the Gemini AI assistant\n"
            "  help                  — this message"
        )

    return f"unknown command: {cmd!r}  (try 'help')"


# ----------------------------- AI Assist -------------------------
@app.post("/api/ai-assist")
async def ai_assist(req: dict):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="AI not configured.")

    network_context = req.get("network_context", "")
    system_prompt = (
        "You are an expert NOC AI assistant. Provide concise, technical "
        "troubleshooting advice based on live device telemetry.\n"
        "Current network state:\n" + str(network_context)
    )

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

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, _call_gemini, system_prompt, api_messages
    )

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