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
