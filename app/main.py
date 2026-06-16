from fastapi import FastAPI
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
	"network": psutil.net_io_counters()._asdict()
    }

@app.get("/docker")
def docker_status():
    return get_containers()
