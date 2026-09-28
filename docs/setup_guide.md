# Setup Guide — Jev Autonomous Eval Harness

## Prerequisites
Docker ≥ 24, Python ≥ 3.11, Node ≥ 18 (only for local dev), a GitHub **fine-grained PAT with `repo` scope**.

## One-command launch
```bash
git clone https://github.com/<org>/jev-autonomous-eval-harness && cd jev-autonomous-eval-harness
export GITHUB_TOKEN=ghp_xxx          # scoped PAT for Phase 7 auto-push — never committed
export JEV_JWT_SECRET=$(openssl rand -hex 16)
docker compose up --build
```
Open http://localhost:5173. Login: `admin` / `jev-default` (rotate immediately in ⚙️ Admin).

## GitHub token configuration
1. Create PAT at github.com/settings/token → scopes: `repo` only, expiry ≤90 days.
2. Local: `export GITHUB_TOKEN=...` (read from env by `jev_orchestrator/github_pusher.py`).
3. CI: repo secret `GITHUB_TOKEN` consumed by `.github/workflows/jev-autopilot.yml`.
4. The pusher creates/updates repo `jev-autonomous-eval-harness`, force-pushes `main`, uploads `setup_guide.pdf`/`install_guide.pdf` (converted from these Markdown sources via `md-to-pdf`), tags `v1.0.0-autopilot`.

## Verify
`curl localhost:8000/api/status` → JSON with `running`, `phase`, `repo_url`. Click **▶ Start Autopilot** in 🤖 view; watch graphs in 📊 view.
