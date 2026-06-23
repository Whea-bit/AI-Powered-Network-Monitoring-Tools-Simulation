from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.telemetry import telemetry_engine

router = APIRouter()

@router.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    # 1. Accept the incoming WebSocket connection
    await telemetry_engine.connect(websocket)
    try:
        while True:
            # 2. Keep the channel open and listen for client messages
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        # 3. Clean up safely if the user closes the browser tab
        telemetry_engine.disconnect(websocket)  