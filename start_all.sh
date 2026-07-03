#!/bin/bash

echo "Starting AI-NOC Dashboard..."

cd ~/ai-noc
source venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "Backend started (PID $BACKEND_PID)"

sleep 3

cd ~/ai-noc/frontend
npm start &
FRONTEND_PID=$!
echo "Frontend started (PID $FRONTEND_PID)"

sleep 5

echo "Starting ngrok tunnel..."
ngrok http --url=detonator-coherence-gizmo.ngrok-free.dev 3000

kill $BACKEND_PID $FRONTEND_PID
echo "Stopped backend and frontend."