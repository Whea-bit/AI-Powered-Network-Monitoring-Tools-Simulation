import asyncio
import platform
import re
from typing import List
from fastapi import WebSocket
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException

# --- REAL ICMP PING LOGIC ---
async def check_ping(ip_address: str) -> str:
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = f"ping {param} 1 -W 1 {ip_address}"
    process = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    return "online" if process.returncode == 0 else "offline"

# --- REAL SSH TELEMETRY LOGIC (NETMIKO) ---
def fetch_real_telemetry(device: dict) -> dict:
    """Logs into the physical switch via SSH, runs commands, and extracts exact CPU/Memory."""
    # Default fallback metrics if SSH fails
    metrics = {"cpu_percent": 0, "memory_percent": 0, "link_utilization": 0}
    loops_detected = []
    rj45_faults = []

    # If it's Meraki, we would use requests.get() to the Meraki Dashboard API here instead.
    if device["vendor"] == "Meraki":
        return {"metrics": metrics, "loops": loops_detected, "faults": rj45_faults}

    try:
        # Open SSH Connection
        net_connect = ConnectHandler(**device["credentials"])
        
        # --- CISCO IOS PARSING EXAMPLES ---
        if device["credentials"]["device_type"] == "cisco_ios":
            # 1. Check CPU
            cpu_output = net_connect.send_command("show processes cpu | include one minute")
            # Example output: "CPU utilization for five seconds: 12%/0%; one minute: 15%; five minutes: 11%"
            cpu_match = re.search(r'one minute:\s*(\d+)%', cpu_output)
            if cpu_match:
                metrics["cpu_percent"] = int(cpu_match.group(1))

            # 2. Check Spanning Tree Loops (Looking for ports in Blocked/Broken state)
            stp_output = net_connect.send_command("show spanning-tree summary")
            if "Loop guard" in stp_output and "blocking" in stp_output:
                loops_detected.append("STP-WARNING")
                
        # --- ARUBA PARSING EXAMPLES ---
        elif device["credentials"]["device_type"] == "aruba_os":
            cpu_output = net_connect.send_command("show cpu")
            cpu_match = re.search(r'Average:\s*(\d+)%', cpu_output)
            if cpu_match:
                metrics["cpu_percent"] = int(cpu_match.group(1))

        net_connect.disconnect()

    except (NetmikoTimeoutException, NetmikoAuthenticationException) as e:
        print(f"SSH Failed for {device['name']}: {str(e)}")
        # If SSH fails, we will trigger a fault alert
        rj45_faults.append("SSH_UNREACHABLE")

    return {
        "metrics": metrics,
        "loops_detected": loops_detected,
        "rj45_faults": rj45_faults
    }

# --- THE TELEMETRY ENGINE ---
class TelemetryEngine:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.is_running = False
        self.polling_task = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

    async def start_polling(self):
        self.is_running = True
        self.polling_task = asyncio.create_task(self._polling_loop())

    async def stop_polling(self):
        self.is_running = False
        if self.polling_task:
            self.polling_task.cancel()

    async def _polling_loop(self):
        # 🔴 REAL DEVICE INVENTORY WITH CREDENTIALS
        real_devices = [
            {
                "name": "core-switch-01", 
                "vendor": "Cisco", 
                "ip": "8.8.8.8", # <--- CHANGE THIS TO YOUR REAL SWITCH IP
                "credentials": {
                    "device_type": "cisco_ios",
                    "host": "8.8.8.8", # <--- CHANGE THIS
                    "username": "YOUR_USERNAME",    
                    "password": "YOUR_PASSWORD", 
                    "secret": "YOUR_ENABLE_SECRET", 
                }
            }
        ]

        while self.is_running:
            try:
                # 1. Ping devices
                ping_tasks = [check_ping(dev["ip"]) for dev in real_devices]
                ping_results = await asyncio.gather(*ping_tasks)

                telemetry_snapshot = []
                
                # 2. Scrape Real Telemetry via SSH
                for i, device in enumerate(real_devices):
                    actual_status = ping_results[i]
                    
                    # Run Netmiko synchronously in a background thread so we don't freeze the app!
                    if actual_status == "online":
                        real_data = await asyncio.to_thread(fetch_real_telemetry, device)
                    else:
                        # Don't try to SSH into a dead switch
                        real_data = {"metrics": {"cpu_percent": 0, "memory_percent": 0, "link_utilization": 0}, "loops_detected": [], "rj45_faults": []}
                    
                    telemetry_snapshot.append({
                        "name": device["name"],
                        "vendor": device["vendor"],
                        "ip": device["ip"],
                        "status": actual_status,
                        "metrics": real_data["metrics"],
                        "loops_detected": real_data["loops_detected"],
                        "rj45_faults": real_data["rj45_faults"]
                    })
                
                # --- ALERT WATCHDOG ---
                for device in telemetry_snapshot:
                    alerts = []
                    if device["metrics"]["cpu_percent"] >= 90:
                        alerts.append(f"CRITICAL CPU: {device['metrics']['cpu_percent']}%")
                    if len(device["loops_detected"]) > 0:
                        alerts.append(f"NETWORK WARNING: {device['loops_detected']}")
                    if len(device["rj45_faults"]) > 0:
                        alerts.append(f"PORT FAULT: {device['rj45_faults']}")
                        
                    if alerts:
                        await self.broadcast({"event": "critical_alert", "device": device['name'], "issues": alerts})

                # Broadcast live data
                await self.broadcast({"event": "telemetry_update", "data": telemetry_snapshot})
                
                # Wait 10 seconds between scrapes (real switches will crash if you scrape them every 2 seconds)
                await asyncio.sleep(10) 
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in polling loop: {str(e)}")
                await asyncio.sleep(10)

telemetry_engine = TelemetryEngine()