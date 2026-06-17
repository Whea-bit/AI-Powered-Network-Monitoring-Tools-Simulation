from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import psutil
from app.docker_monitor import get_containers

app = FastAPI()

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

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI-NOC Dashboard</title>

        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
                font-family: Arial, sans-serif;
            }

            body {
                background: #0f1117;
                color: white;
                padding: 20px;
            }

            h1 {
                margin-bottom: 25px;
            }

            .grid {
                display: grid;9
                grip-template-column: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 25px;
            }

            .card {
                background: #1c1f26;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.3);
            }

            .card-title {
                color: #9aa4b2;
                font-size: 14px;
                margin-bottom: 10px;
                text-transform: uppercase;
            }

            .metric {
                font-size: 36px;
                font-weight: bold;
            }

            .progress {
                 margin-top: 15px;
                 width: 100%;
                 height: 12px;
                 background: #333;
                 border-radius: 10px;
                 overflow: hidden;
            }

            .progress-bar {
                 height: 100%;
                 transition: width 0.5s ease;
            }

            .green {
                 background: #2ecc71;
            }

            .yellow {
                 background: #f1c40f;
            }

            .red {
                 background: #e74c3c;
            }

            .status-box {
                 background: #1c1f26;
                 border-radius: 12px;
                 padding: 20px;
                 margin-bottom: 20px;
            }

            .status-text {
                 display: inline-block;
                 padding: 10px 18px;
                 border-radius: 8px;
                 font-weight: bold;
                 margin-top: 10px;
            }

            .network-box {
                 background: #1c1f26;
                 border-radius: 12px;
                 padding: 20px;
            }

            table {
                 width: 100%;
                 border-collapse: collapse;
            }

            td {
                 padding: 10px;
                 border-bottom: 1px solid #333;
            }

            td:first-child {
                 color: #9aa4b2;
            }

            .footer {
                 margin-top: 20px;
                 color: #777;
                 text-align: center;
            }
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

                  <div class="progress">
                     <div id="cpuBar" class="progress-bar green"></div>
                  </div>
              </div>

              <div class="card">
                  <div class="card-title">Memory Usage</div>
                  <div id="memoryValue" class="metric">0%</div>

                  <div class="progress">
                      <div id="memoryBar" class="progress-bar green"></div>
                  </div>
               </div>

               <div class="card">
                   <div class="card-title">Disk Usage</div>
                   <div id="diskValue" class="metric">0%</div>

                   <div class="progress">
                       <div id="diskBar" class="progress-bar green"></div>
                   </div>
               </div>

               <div class="card">
                   <div class="card-title">Docker Container</div>
                   <div id="dockerCount" class="metric">0</div>
               </div>

            </div>

            <div class="network-box">
                <h2>Network Statistics</h2>

                <table>
                    <tr>
                        <td>Bytes Sent</td>
                        <td id="bytesSent">0</td>
                    </tr>

                    <tr>
                        <td>Bytes Received</td>
                        <td id="bytesRecv">0</td>
                    </tr>

                    <tr>
                        <td>Packets Sent</td>
                        <td id ="packetsSent">0</td>
                    </tr>

                    <tr>
                        <td>Packets Received</td>
                        <td id="packetsRecv">0</td>
                    </tr>
                </table>
            </dive>

            <div class="footer">
                Auto-refresh every 3 seconds
            </div>

            <script>

                function getColor(value) {
                    if (value >= 80 return "red";
                    if (value >= 60 return "yellow";
                    return "green";
                }

                function getOverall(cpu, mem, disk) {

                    if (cpu >= 80 || mem >= 80 || disk >= 80) {
                       return "CRITICAL";
                    }

                    if (cpu >= 60 || mem >= 60 || disk >= 60) {
                       return "WARNING";
                    }

                    return "HEALTHY";
                }

                async function loadData() {

                    const system =
                        await fetch('/system').then(r => r.json());

                    const docker =
                        await fetch('/docker').then(r => r.json());

                    const cpu = system.cpu_percent;
                    const memory = system.memory_percent;
                    const disk = system.disk_percent;

                    document.getElementById("cpuValue").innerText =
                        cpu.toFixed(1) + "%";

                    document.getElemetById("memoryValue").innerText =
                        memory.toFixed(1) + "%";

                    document.getElementById("diskValue").innerText =
                        disk.toFixed(1) + "%";

                    document.getElementById("dockerCount").innerText =
                        docker.length;

                   const cpuBar =
                       document.getElementById("cpuBar");

                   cpuBar.style.width = cpu + "%";
                   cpuBar.className =
                       "progress-bar " + getColor(cpu);

                   const memoryBar =
                       document.getElementById("memoryBar");

                   memoryBar.style.width = memory + "%";
                   memoryBar.classmate =
                       "progress-bar" + getColor(memory);

                   const diskBar =
                       document.getElementById("diskBar");

                   diskBar.style.width = disk + "%";
                   diskBar.classmate =
                       "progress-bar " + getColor(disk);

                   document.getElementById("bytesSent").innerText =
                       system.network.bytes_sent.toLocaleString();

                   document.getElementById("bytesRecv").innerText =
                       system.network.packets_sent.toLocaleString();

                   document.getElemntById("packetRecv").innerText =
                       system.network.packets_recv.toLocaleString();

                   const overall =
                      getOverall(cpu, memory, disk);

                   let statusColor = "green";

                   if (overall === "WARNING")
                       statusColor = "yellow";

                   if (overall === "CRITICAL")
                       statusColor = "red";

                   document.getElementById("overallStatus").innerHTML =
                       `<span class="status-text ${statusColor}">
                           ${overall}
                        </span>`;
               }

               loadData();
               setInterval(loadData, 3000);

        </script>

    </body>
    </html>
    """
