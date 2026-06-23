import subprocess
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Web CLI"])

class CommandRequest(BaseModel):
    command: str

@router.post("/api/cli")
async def execute_command(req: CommandRequest):
    # 1. Security Whitelist: Only allow specific, safe read-only commands
    allowed_commands = ["ping", "ls", "pwd", "echo", "ip", "ifconfig", "df", "free", "uptime"]
    
    cmd_parts = req.command.split()
    if not cmd_parts:
        return {"output": ""}
        
    base_cmd = cmd_parts[0].lower()

    if base_cmd not in allowed_commands:
        return {"output": f"🔒 Security Policy: Command '{base_cmd}' is blocked.\nAllowed commands: {', '.join(allowed_commands)}"}

    try:
        # 2. Add a limit to ping so it doesn't run forever and crash the server
        if base_cmd == "ping" and "-c" not in cmd_parts:
            cmd_parts.insert(1, "-c")
            cmd_parts.insert(2, "4") # Ping 4 times by default

        # 3. Execute the command on your actual WSL Linux OS
        result = subprocess.run(
            cmd_parts,
            capture_output=True,
            text=True,
            timeout=10 # Kill it if it takes longer than 10 seconds
        )
        
        output = result.stdout if result.stdout else result.stderr
        return {"output": output}
        
    except subprocess.TimeoutExpired:
        return {"output": "⏳ Command timed out after 10 seconds."}
    except Exception as e:
        return {"output": f"⚠️ Error executing command: {str(e)}"}