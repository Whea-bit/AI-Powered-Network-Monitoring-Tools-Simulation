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
    <html>
    <head>
        <title>AI-NOC Dashboard</title>
        <style>
            body {
                font-family: Arial;
                background: #0f1117;
                color: white;
                padding: 20px;
            }

            h1 { color: #00fcc; }

            .card {
                background: #1c1f26;
                padding: 15px;
                margin: 10px 0;
                border-radius: 10px;
            }

            pre {
                background: #111;
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
            }

            .status {
                padding: 5px 10px;
                border-radius: 5px;
                display: inline-block;
            }

            .green { background: #2ecc71; }
            .yellow { background: #f1c40f; }
            .red { background: #e74c3c; }
        </style>
    </head>

    <body>
        <h1>AI-NOC Dashboard</h1>

        <div class="card">
            <h2>System Metrics</h2>
            <div id="status"></div>
            <pre id="system">Loading...</pre>
        </div>

        <div class="card">
            <h2>Docker Containers</h2>
            <pre id="docker">Loading...</pre>
        </div>

        <script>
            function getStatus(cpu, mem) {
                if (cpu > 80 || mem > 80) return "red";
                if (cpu > 60 || mem > 60) return "yellow";
                return "green";
            }

            async function loadData() {
                const sys = await fetch('/system').then(r => r.json());
                const docker = await fetch('/docker').then(r => r.json());

                document.getElementById('system').innerText =
                    JSON.stringify(sys, null, 2);

                document.getElementById('docker').innerText =
                    JSON.stringify(docker, null, 2);

                const status = getStatus(sys.cpu_percent, sys.memory_percent);

                document.getElementById('status').innerHTML =
                    `<span class="status ${status}">${status.toUpperCase()}</span>`;
            }

            setInterval(loadData, 3000);
            loadData();
        </script>
    </body>
    </html>
    """



