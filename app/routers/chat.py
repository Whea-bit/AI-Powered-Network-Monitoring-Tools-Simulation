import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI
from app.services.telemetry import telemetry_engine

router = APIRouter(tags=["AI Assistant"])

# ⚠️ INSTRUCTION: Paste your real OpenAI API key right here
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "sk-your-openai-api-key-here")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

class ChatMessage(BaseModel):
    message: str

@router.post("/api/chat")
async def process_chat(chat_in: ChatMessage):
    # Security check to ensure the API key was added
    if not OPENAI_API_KEY or OPENAI_API_KEY == "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":
         return {"reply": "⚠️ **System Alert:** OpenAI API Key not configured. Please add your key to `app/routers/chat.py`."}
    
    try:
        # 1. RAG (Retrieval): Grab the absolute latest network state from the polling engine
        live_network_state = telemetry_engine._generate_mock_network_telemetry()
        
        # 2. Augmentation: Inject the live data into the AI's System Prompt
        system_prompt = f"""You are the AI-NOC, an elite Senior Network Engineer.
        You are directly monitoring a multi-vendor network (Cisco, FortiGate, Aruba, Meraki).
        
        Here is the LIVE JSON snapshot of the network RIGHT NOW:
        {json.dumps(live_network_state, indent=2)}
        
        Rules:
        - Keep your answers concise, highly technical, and directly related to the live data.
        - If the user asks about faults, loops, or high CPU, look at the JSON and tell them EXACTLY which device and port is failing.
        - Use markdown (bolding, bullet points) for readability.
        - Do not hallucinate; if the data says the network is healthy, confirm it is healthy.
        """

        # 3. Generation: Call OpenAI to analyze the data and answer the user
        response = await client.chat.completions.create(
            model="gpt-4o-mini", # Fast and extremely capable for JSON logic
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chat_in.message}
            ],
            max_tokens=300,
            temperature=0.2 # Low temperature keeps the AI factual and analytical
        )
        
        return {"reply": response.choices[0].message.content}
        
    except Exception as e:
        return {"reply": f"⚠️ **AI Engine Error:** {str(e)}"}