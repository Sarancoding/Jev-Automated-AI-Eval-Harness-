import React, { useEffect, useState } from "react";
import { Landing, Control, Metrics, Gate, Security, Docs, Admin } from "./components/views.jsx";

const VIEWS = [["Landing", Landing], ["Autopilot", Control], ["Metrics", Metrics], ["Gate", Gate], ["Security", Security], ["Docs", Docs], ["Admin", Admin]];

/** Root dashboard shell: login, WebSocket live feed, 7-view router. */
export default function App() {
  const [token, setToken] = useState(localStorage.getItem("jev_tok") || "");
  const [user, setUser] = useState("");
  const [pw, setPw] = useState("");
  const [view, setView] = useState("Landing");
  const [live, setLive] = useState({});

  useEffect(() => {
    let ws, alive = true;
    const connect = () => {
      ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
      ws.onmessage = (e) => alive && setLive(JSON.parse(e.data));
      ws.onclose = () => alive && setTimeout(connect, 2000);
    };
    connect();
    return () => { alive = false; ws?.close(); };
  }, []);

  const login = async () => {
    const body = new URLSearchParams({ username: user, password: pw });
    const r = await fetch("/token", { method: "POST", body });
    if (r.ok) { const d = await r.json(); localStorage.setItem("jev_tok", d.access_token); setToken(d.access_token); }
  };
  const logout = () => { localStorage.removeItem("jev_tok"); setToken(""); };

  const Active = (VIEWS.find((v) => v[0] === view) || VIEWS[0])[1];
  return (<div style={{ fontFamily: "system-ui", background: "#111", color: "#eee", minHeight: "100vh" }}>
    <header style={{ display: "flex", gap: 8, padding: 10, background: "#1b1b1b" }}>
      <strong>🤖 Jev Control Room</strong>
      {VIEWS.map(([n]) => <button key={n} onClick={() => setView(n)} style={{ background: view === n ? "#4caf50" : "#333", color: "#fff", border: 0, padding: "6px 10px", cursor: "pointer" }}>{n}</button>)}
      <span style={{ marginLeft: "auto" }}>{live.running ? "🟢 running" : "⚪ idle"} · {live.phase || ""}</span>
      {token ? <button onClick={logout}>Logout</button> : null}
    </header>
    {!token && (<div style={{ padding: 16, borderBottom: "1px solid #333" }}>
      <input placeholder="username (admin/operator/viewer)" value={user} onChange={(e) => setUser(e.target.value)} />{" "}
      <input placeholder="password (jev-default)" type="password" value={pw} onChange={(e) => setPw(e.target.value)} />{" "}
      <button data-testid="login-btn" onClick={login}>Login</button>
    </div>)}
    <main style={{ padding: 16 }}>
      <Active token={token} live={live} />
    </main>
  </div>);
}
