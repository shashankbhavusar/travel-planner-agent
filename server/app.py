from fastapi import FastAPI
from pydantic import BaseModel
from pathlib import Path
import sys

# ensure project root is on sys.path so we can import existing modules
sys.path.append(str(Path(__file__).resolve().parents[1]))

from agent.supervisor import general_chat, supervisor
from agent.travel_agent import travel_agent
from agent.supervisor_memory import load_messages, save_conversation

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Travel Planner Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}


class MessageRequest(BaseModel):
    user_id: str
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/history")
async def get_history(user_id: str):
    return {"messages": load_messages(user_id)}


@app.post("/api/message")
async def handle_message(req: MessageRequest):
    session = sessions.get(req.user_id, {"active_agent": None})

    decision = supervisor(req.message, session)

    if decision.get("route") == "travel":
        result = travel_agent(user_id=req.user_id, message=req.message)
        save_conversation(req.user_id, req.message, result.get("response"))
        if result.get("trip_finished"):
            session["active_agent"] = None
        sessions[req.user_id] = session
        return result

    else:
        answer = general_chat(req.user_id, req.message)
        save_conversation(req.user_id, req.message, answer)
        sessions[req.user_id] = session
        return {"response": answer}
