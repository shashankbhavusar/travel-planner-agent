# Frontend (Vite + React)

This is a full React app scaffolded for fast local development with Vite.

Setup:

```
cd frontend
npm install
```

Run (development):

```
npm run dev
```

Build:

```
npm run build
npm run preview
```

Usage:

- The app runs on `http://localhost:5173` by default using Vite.
- It POSTs to `http://localhost:8000/api/message` for the agent — ensure the backend is running.
- `User ID` and conversation are persisted in `localStorage` so the agent continues sessions when you refresh.
