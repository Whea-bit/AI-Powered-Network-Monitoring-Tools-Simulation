from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import psutil
from contextlib import asynccontextmanager

# --- REAL-TIME ENGINE IMPORTS ---
from app.routers import ws_endpoints
from app.services.telemetry import telemetry_engine
from app.docker_monitor import get_containers
from app.device_inventory import get_devices, add_device

# --- BACKGROUND TASK MANAGER ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    await telemetry_engine.start_polling()
    yield
    await telemetry_engine.stop_polling()

# --- INITIALIZATION ---
app = FastAPI(title="AI-NOC Monitoring Engine", lifespan=lifespan)
app.include_router(ws_endpoints.router)

class Device(BaseModel):
    name: str
    vendor: str
    ip: str
    location: str

# --- REST APIS ---
@app.get("/")
def root():
    return {"status": "AI-NOC running"}

@app.get("/system")
def system():
    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "network": psutil.net_io_counters()._asdict()
    }

@app.get("/docker")
def docker_status():
    return get_containers()

@app.get("/devices")
def list_devices():
    return get_devices()

@app.post("/devices")
def create_device(device: Device):
    return add_device(device.dict())

# --- DASHBOARD UI ---
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI-NOC Dashboard</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; font-family: Arial, sans-serif; }
            body { background: #0f1117; color: white; padding: 20px; }
            h1 { margin-bottom: 25px; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 25px; }
            .card { background: #1c1f26; border-radius: 12px; padding: 20px; box-shadow: 0 4px 10px rgba(0,0,0,0.3); }
            .card-title { color: #9aa4b2; font-size: 14px; margin-bottom: 10px; text-transform: uppercase; }
            .metric { font-size: 36px; font-weight: bold; }
            .progress { margin-top: 15px; width: 100%; height: 12px; background: #333; border-radius: 10px; overflow: hidden; }
            .progress-bar { height: 100%; transition: width 0.5s ease; }
            .green { background: #2ecc71; }
            .yellow { background: #f1c40f; }
            .red { background: #e74c3c; }
            .status-box { background: #1c1f26; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
            .status-text { display: inline-block; padding: 10px 18px; border-radius: 8px; font-weight: bold; margin-top: 10px; }
            .network-box { background: #1c1f26; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; }
            td, th { padding: 10px; border-bottom: 1px solid #333; }
            td:first-child { color: #9aa4b2; }
            .footer { margin-top: 20px; color: #777; text-align: center; }
        </style>
    </head>
    <body>
         <h1> AI-NOC Dashboard</h1>

         <div class="status-box">
             <h2>Overall Health</h2>
             <div id="overallStatus"></div>
         </div>

         <div class="grid">
              <div class="card">
                  <div class="card-title">CPU Usage</div>
                  <div id="cpuValue" class="metric">0%</div>
                  <div class="progress"><div id="cpuBar" class="progress-bar green"></div></div>
              </div>
              <div class="card">
                  <div class="card-title">Memory Usage</div>
                  <div id="memoryValue" class="metric">0%</div>
                  <div class="progress"><div id="memoryBar" class="progress-bar green"></div></div>
               </div>
               <div class="card">
                   <div class="card-title">Disk Usage</div>
                   <div id="diskValue" class="metric">0%</div>
                   <div class="progress"><div id="diskBar" class="progress-bar green"></div></div>
               </div>
               <div class="card">
                   <div class="card-title">Docker Container</div>
                   <div id="dockerCount" class="metric">0</div>
               </div>
            </div>

            <div class="network-box">
                <h2>Network Statistics</h2>
                <table>
                    <tr><td>Bytes Sent</td><td id="bytesSent">0</td></tr>
                    <tr><td>Bytes Received</td><td id="bytesRecv">0</td></tr>
                    <tr><td>Packets Sent</td><td id ="packetsSent">0</td></tr>
                    <tr><td>Packets Received</td><td id="packetsRecv">0</td></tr>
                </table>
            </div>

            <div class="network-box">
                <h2>Live Device Telemetry</h2>
                <table style="margin-top: 15px;">
                    <thead>
                        <tr>
                            <th style="text-align:left; color:#9aa4b2;">Device Name</th>
                            <th style="text-align:left; color:#9aa4b2;">Vendor</th>
                            <th style="text-align:center; color:#9aa4b2;">Status</th>
                            <th style="text-align:center; color:#9aa4b2;">CPU</th>
                            <th style="text-align:center; color:#9aa4b2;">Memory</th>
                            <th style="text-align:center; color:#9aa4b2;">Link Util</th>
                            <th style="text-align:left; color:#9aa4b2;">Active Alerts</th>
                        </tr>
                    </thead>
                    <tbody id="deviceTableBody">
                        <tr><td colspan="7" style="text-align:center; color:#777; padding:20px;">Waiting for WebSocket telemetry stream...</td></tr>
                    </tbody>
                </table>
            </div>

            <div class="footer">Auto-refresh REST APIs every 3 seconds | WebSocket Stream Active</div>

            <script>
                function getColor(value) {
                    if (value >= 80) return "red";
                    if (value >= 60) return "yellow";
                    return "green";
                }

                function getOverall(cpu, mem, disk) {
                    if (cpu >= 80 || mem >= 80 || disk >= 80) return "CRITICAL";
                    if (cpu >= 60 || mem >= 60 || disk >= 60) return "WARNING";
                    return "HEALTHY";
                }

                async function loadData() {
                    const system = await fetch('/system').then(r => r.json());
                    const docker = await fetch('/docker').then(r => r.json());

                    const cpu = system.cpu_percent;
                    const memory = system.memory_percent;
                    const disk = system.disk_percent;

                    document.getElementById("cpuValue").innerText = cpu.toFixed(1) + "%";
                    document.getElementById("memoryValue").innerText = memory.toFixed(1) + "%";
                    document.getElementById("diskValue").innerText = disk.toFixed(1) + "%";
                    document.getElementById("dockerCount").innerText = docker.length;

                   const cpuBar = document.getElementById("cpuBar");
                   cpuBar.style.width = cpu + "%";
                   cpuBar.className = "progress-bar " + getColor(cpu);

                   const memoryBar = document.getElementById("memoryBar");
                   memoryBar.style.width = memory + "%";
                   memoryBar.className = "progress-bar " + getColor(memory);

                   const diskBar = document.getElementById("diskBar");
                   diskBar.style.width = disk + "%";
                   diskBar.className = "progress-bar " + getColor(disk);

                   document.getElementById("bytesSent").innerText = system.network.bytes_sent.toLocaleString();
                   document.getElementById("bytesRecv").innerText = system.network.bytes_recv.toLocaleString();
                   document.getElementById("packetsSent").innerText = system.network.packets_sent.toLocaleString();
                   document.getElementById("packetsRecv").innerText = system.network.packets_recv.toLocaleString();

                   const overall = getOverall(cpu, memory, disk);
                   let statusColor = overall === "WARNING" ? "yellow" : overall === "CRITICAL" ? "red" : "green";

                   document.getElementById("overallStatus").innerHTML = `<span class="status-text ${statusColor}">${overall}</span>`;
                }

                loadData();
                setInterval(loadData, 3000);

                // --- 🟢 REAL-TIME WEBSOCKET ENGINE ---
                const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const socket = new WebSocket(`${wsProtocol}//${window.location.host}/ws/telemetry`);

                socket.onmessage = (event) => {
                    const payload = JSON.parse(event.data);
                    
                    if (payload.event === "telemetry_update") {
                        const tbody = document.getElementById("deviceTableBody");
                        tbody.innerHTML = ""; // Clear old data
                        
                        payload.data.forEach(dev => {
                            // Format status badge
                            const statusColor = dev.status === "online" ? "#2ecc71" : "#f1c40f";
                            const statusBadge = `<span style="background:${statusColor}; color:#000; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px;">${dev.status.toUpperCase()}</span>`;
                            
                            // Format dynamic alerts
                            let alerts = "";
                            if (dev.loops_detected.length > 0) {
                                alerts += `<span style="background:#e74c3c; color:white; padding:3px 6px; border-radius:4px; font-size:11px; margin-right:5px;">STP LOOP: Port ${dev.loops_detected.join(',')}</span>`;
                            }
                            if (dev.rj45_faults.length > 0) {
                                alerts += `<span style="background:#e67e22; color:white; padding:3px 6px; border-radius:4px; font-size:11px;">TDR FAULT: Port ${dev.rj45_faults.join(',')}</span>`;
                            }
                            if (alerts === "") alerts = "<span style='color:#555;'>No faults</span>";

                            // Create Row
                            const row = `
                                <tr>
                                    <td style="font-weight:bold; color:white;">${dev.name}</td>
                                    <td style="color:white;">${dev.vendor}</td>
                                    <td style="text-align:center;">${statusBadge}</td>
                                    <td style="text-align:center; color:${getColor(dev.metrics.cpu_percent)}; font-weight:bold;">${dev.metrics.cpu_percent}%</td>
                                    <td style="text-align:center; color:${getColor(dev.metrics.memory_percent)}; font-weight:bold;">${dev.metrics.memory_percent}%</td>
                                    <td style="text-align:center; color:white;">${dev.metrics.link_utilization}%</td>
                                    <td>${alerts}</td>
                                </tr>
                            `;
                            tbody.innerHTML += row;
                        });
                    }
                };
        </script>
    </body>
    </html>
    """