"""FastAPI backend: JWT/OAuth2-style auth, RBAC, WebSocket live metrics, autopilot control."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import asyncio
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from jev_orchestrator.autopilot import JevAutopilot, STATE_FILE, AUDIT_FILE

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "webapp" / "backend" / "state" / "app.db"
SECRET = os.environ.get("JEV_JWT_SECRET", secrets.token_hex(16))
SESSION_TTL = 3600
ROLE_RANK = {"viewer": 0, "operator": 1, "admin": 2}

app = FastAPI(title="Jev Autopilot Dashboard API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)
autopilot = JevAutopilot(root=ROOT)


def _db() -> sqlite3.Connection:
    """Open SQLite state DB and bootstrap schema + default users."""
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY, pw TEXT, salt TEXT, role TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS tokens(user TEXT, exp REAL)")
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        for name, role in (("admin", "admin"), ("operator", "operator"), ("viewer", "viewer")):
            salt = secrets.token_hex(8)
            con.execute("INSERT INTO users VALUES(?,?,?,?)", (name, hashlib.sha256(f"{salt}:{name}:jev-default".encode()).hexdigest(), salt, role))
        con.commit()
    return con


def _hash(pw: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{pw}".encode()).hexdigest()


def _issue_token(user: str) -> str:
    """Create signed stateless token: user.exp.hmac."""
    exp = time.time() + SESSION_TTL
    payload = f"{user}.{exp:.0f}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{sig}"


def _verify(token: str | None) -> str:
    """Validate token signature/expiry; raise 401 otherwise."""
    if not token or token.count(".") != 2:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    user, exp, sig = token.rsplit(".", 2)
    if not hmac.compare_digest(sig, hmac.new(SECRET.encode(), f"{user}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad signature")
    if float(exp) < time.time():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    return user


def require(role: str):
    """RBAC dependency factory enforcing minimum role rank."""
    def dep(token: str = Depends(oauth2_scheme)) -> str:
        user = _verify(token)
        con = _db()
        row = con.execute("SELECT role FROM users WHERE name=?", (user,)).fetchone()
        if not row or ROLE_RANK[row[0]] < ROLE_RANK[role]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Requires {role}")
        return user
    return dep


class Cred(BaseModel):
    username: str
    password: str


class StartReq(BaseModel):
    domain_docs: str = "Compliance policy for financial reporting, medical triage SLAs, legal discovery, code review gates."
    threshold: float = 0.9


class ThresholdReq(BaseModel):
    threshold: float | None = None


class UserReq(BaseModel):
    name: str
    role: str
    password: str | None = None


@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()) -> dict:
    """OAuth2 password-flow endpoint issuing HMAC-signed session tokens."""
    con = _db()
    row = con.execute("SELECT pw,salt FROM users WHERE name=?", (form.username,)).fetchone()
    if not row or not hmac.compare_digest(row[0], _hash(form.password, row[1])):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return {"access_token": _issue_token(form.username), "token_type": "bearer"}


@app.get("/api/status")
def status_() -> dict:
    """Landing view: system status, repo badge URL, docs list, SECURITY summary."""
    st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    sec_md = (ROOT / "SECURITY.md")
    return {"running": bool(st.get("running")), "phase": st.get("phase"), "repo_url": st.get("repo_url", ""),
            "updated_at": st.get("updated_at", 0), "security_summary": sec_md.read_text()[:600] if sec_md.exists() else "",
            "docs": ["README.md", "CONTRIBUTING.md", "SECURITY.md", "docs/setup_guide.md", "docs/install_guide.md"]}


@app.get("/api/metrics")
def metrics() -> dict:
    """Live metrics payload powering the three Plotly graphs + counters."""
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"metrics": {}, "history": []}


@app.post("/api/autopilot/start")
def start(req: StartReq, user: str = Depends(require("operator"))) -> dict:
    """Manual/admin trigger of the full autonomous cycle."""
    autopilot.start_async(req.domain_docs, req.threshold)
    return {"started": True, "by": user}


@app.post("/api/autopilot/stop")
def stop(user: str = Depends(require("operator"))) -> dict:
    """Signal the autopilot to halt at next phase boundary."""
    autopilot.stop()
    return {"stopping": True, "by": user}


@app.post("/api/autopilot/threshold")
def threshold(req: ThresholdReq, user: str = Depends(require("operator"))) -> dict:
    """Override gate threshold consumed by calibration/eval loops."""
    autopilot.set_threshold(req.threshold)
    return {"threshold": req.threshold, "by": user}


@app.get("/api/gate")
def gate() -> dict:
    """CI/CD gate monitor: current blocked reasons + historical pass/fail rates."""
    st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {"history": [], "blocked_reasons": []}
    cycles = [h for h in st.get("history", []) if h["event"] == "cycle_complete"]
    passed = sum(1 for c in cycles if not c.get("blocked"))
    return {"blocked_reasons": st.get("blocked_reasons", []), "cycles": len(cycles),
            "pass_rate": round(passed / max(1, len(cycles)), 3), "phase": st.get("phase")}


@app.get("/api/security")
def security(user: str = Depends(require("viewer"))) -> dict:
    """Security Center: sanitized scan results + tail of immutable audit log."""
    st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    lines = AUDIT_FILE.read_text().splitlines()[-100:] if AUDIT_FILE.exists() else []
    return {"scan": st.get("metrics", {}).get("security", {}), "audit": [json.loads(l) for l in lines]}


@app.get("/api/docs/{name}")
def docs(name: str) -> dict:
    """Docs Hub content loader with path traversal protection."""
    safe = {"README.md": "README.md", "CONTRIBUTING.md": "CONTRIBUTING.md", "SECURITY.md": "SECURITY.md",
            "setup_guide.md": "docs/setup_guide.md", "install_guide.md": "docs/install_guide.md", "RESULTS.md": "RESULTS.md"}
    if name not in safe:
        raise HTTPException(404, "Unknown document")
    p = ROOT / safe[name]
    return {"name": name, "markdown": p.read_text() if p.exists() else ""}


@app.get("/api/admin/users")
def users(user: str = Depends(require("admin"))) -> list[dict]:
    """Admin: list users/roles."""
    con = _db()
    return [{"name": n, "role": r} for n, r in con.execute("SELECT name,role FROM users")]


@app.post("/api/admin/users")
def put_user(req: UserReq, user: str = Depends(require("admin"))) -> dict:
    """Admin: create/update user, rotate secret or demote role."""
    if req.role not in ROLE_RANK:
        raise HTTPException(422, "Bad role")
    con = _db()
    salt = secrets.token_hex(8)
    pw = _hash(req.password or "jev-default", salt)
    con.execute("INSERT OR REPLACE INTO users VALUES(?,?,?,?)", (req.name, pw, salt, req.role))
    con.commit()
    return {"ok": True, "rotated_by": user}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    """Push dashboard state every second while connected (auto-refresh graphs)."""
    await websocket.accept()
    try:
        while True:
            st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
            await websocket.send_json({"ts": time.time(), "running": st.get("running"), "phase": st.get("phase"),
                                       "metrics": st.get("metrics", {}), "blocked_reasons": st.get("blocked_reasons", []),
                                       "recent": st.get("history", [])[-20:]})
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
