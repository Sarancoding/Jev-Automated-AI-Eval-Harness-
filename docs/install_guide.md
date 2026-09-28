# Install Guide

## Dockerized (recommended)
```bash
docker compose up -d          # backend :8000, frontend :5173, shared ./webapp/backend/state volume
docker compose logs -f backend
```

## Manual
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # pinned deps, scanned by Phase 5 pip-audit
uvicorn webapp.backend.main:app --port 8000 &
cd webapp/frontend && npm install && npm run dev    # Vite proxies /api + /ws to :8000
pytest tests/test_autopilot.py            # end-to-end loop validation
```

## Troubleshooting
- `401 session expired` → tokens last 1h; re-login.
- Phase 7 skip → `GITHUB_TOKEN` missing/expired; set env and restart backend.
- Empty graphs → no run yet; press ▶ Start Autopilot (operator role required).
