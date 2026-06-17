# Server (FastAPI)

Run the backend API which exposes the travel planner agent integration.

Install dependencies:

```
python -m pip install -r server/requirements.txt
```

Run the server (from project root):

```
uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:

- `GET /health` - simple health check
- `POST /api/message` - body: `{ "user_id": "user1", "message": "Hello" }` returns agent response
