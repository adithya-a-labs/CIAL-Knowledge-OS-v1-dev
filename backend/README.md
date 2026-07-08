# Backend Moved

The FastAPI backend no longer lives at the repository root.

Use:

```powershell
cd services/knowledge-engine
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

The real backend source is `services/knowledge-engine/backend/app`.
