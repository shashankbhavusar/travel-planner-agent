# Travel Planner Agent — UI Integration

This workspace contains the original agent code and a frontend + backend integration.

Quick start:

1. Start the backend API:

```
python -m pip install -r server/requirements.txt
uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

2. Start the frontend (Vite + React):

```
cd frontend
npm install
npm run dev
```

- Open `http://localhost:5173` in your browser (Vite dev server).
- The frontend sends requests to `http://localhost:8000/api/message` by default. Keep the backend running.
- Conversation history is loaded from `GET /api/history?user_id=...` when the frontend starts or the User ID changes.

Notes:

- The backend imports the existing agent functions from the project root. Run the server from the project root so imports resolve correctly.
- Conversation state is kept per `user_id` in memory on the backend; the frontend persists `user_id` and conversation locally so the agent continues from where it left when you reuse the same `user_id`.
- For production use, add authentication, persistent session storage, and a proper build/deployment pipeline.

## Architecture

This app is built as a split frontend/backend service with an AI-powered agent core.

- `frontend/`: React + Vite UI that sends user messages to the backend and displays the agent response.
- `server/app.py`: FastAPI backend exposing `POST /api/message` and `GET /api/history`.
- `agent/supervisor.py`: Routes incoming requests into either the travel planner flow or a general chat flow. It uses the `ChatGroq` LLM to classify intent, keeps track of whether a travel session is active, and selects the correct path.
- `agent/travel_agent.py`: Implements the travel planning pipeline as a LangGraph state machine. This file defines the travel agent's state (`TripState`), the sequence of graph nodes, and the complete flow:
  - `extract_info`: parses the user's travel request into structured trip data using LLM extraction.
  - `check_missing_fields`: validates required trip fields and asks follow-up questions if needed.
  - `get_flight_info`: calls `agent/tools/flight.py` to fetch flight search results based on the trip state.
  - `get_hotels_info`: calls `agent/tools/tavily.py` to fetch hotel recommendations.
  - `get_itenary_info`: generates the final itinerary using the LLM and aggregated travel data.
  - `plan_trip` / `ask_user`: routes either to completion or a follow-up question depending on missing information.
- `agent/tools/flight.py`: Encapsulates flight lookup functionality for the travel agent.
- `agent/tools/tavily.py`: Encapsulates hotel search functionality for the travel agent.
- `agent/supervisor_memory.py`: Saves and loads the user conversation history from a persistence layer, enabling the general chat flow to maintain context and replay past messages.
- `agent/memory.py`: Provides persistence and checkpointing support for the LangGraph agent state across invocations.

### Agent Core Details

The agent core is centered around the `agent/` package:
- `agent/supervisor.py` decides whether a given user message should be handled by the travel planner or by a free-form chat assistant.
- If the route is travel, `agent/travel_agent.py` runs a structured state machine that collects trip details, enriches them with flight and hotel data, and produces an itinerary response.
- If the route is general chat, the system builds a history of past messages from `agent/supervisor_memory.py` and sends those to `ChatGroq` to maintain continuity.
- The travel planner uses a LangGraph `StateGraph` to ensure each step is deterministic and can be checkpointed, while tool calls are isolated in `agent/tools/` modules.

Architecture diagram: `architecture_diagram.svg`
