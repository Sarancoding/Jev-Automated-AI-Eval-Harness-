import React, { useEffect, useState } from "react";
import Plot from "./Plot.jsx";

const PHASES = ["data_gen", "calibration", "eval_execution", "cost_optimization", "security_scan", "dashboard_sync", "github_deploy"];

/** 🏠 Landing: status, README preview, repo badge, SECURITY summary, quick links. */
export function Landing({ live }) {
  const [status, setStatus] = useState({});
  const [readme, setReadme] = useState("");
  useEffect(() => { fetch("/api/status").then((r) => r.json()).then(setStatus); }, [live?.ts]);
  useEffect(() => { fetch("/api/docs/README.md").then((r) => r.json()).then((d) => setReadme(d.markdown || "")).catch(() => {}); }, []);
  return (<section>
    <h2>System Status</h2>
    <p>{status.running ? "🟢 Jev autopilot RUNNING" : "⚪ Idle"} — phase: {status.phase || "n/a"}</p>
    {status.repo_url && <a href={status.repo_url}><img alt="repo" src={`https://img.shields.io/badge/repo-jev--autonomous--eval--harness-blue`} /></a>}
    <h3>README.md</h3>
    <pre data-testid="landing-readme" style={{ whiteSpace: "pre-wrap", maxHeight: 400, overflow: "auto", background: "#1b1b1b", padding: 12 }}>{readme}</pre>
    <h3>SECURITY.md summary</h3><pre style={{ whiteSpace: "pre-wrap" }}>{status.security_summary}</pre>
    <h3>Guide PDFs</h3><ul><li><a href="/docs/setup_guide.pdf">setup_guide.pdf</a></li><li><a href="/docs/install_guide.pdf">install_guide.pdf</a></li></ul>
  </section>);
}

/** 🤖 Autopilot control: start/stop, threshold override, decision log. */
export function Control({ token, live }) {
  const [thr, setThr] = useState(0.9);
  const auth = { headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" } };
  const post = (url, body) => fetch(url, { method: "POST", ...auth, body: body ? JSON.stringify(body) : undefined }).then((r) => r.json());
  return (<section>
    <h2>Jev Autopilot Control</h2>
    <button data-testid="start-btn" onClick={() => post("/api/autopilot/start", { threshold: thr })}>▶ Start Autopilot</button>{" "}
    <button onClick={() => post("/api/autopilot/stop")}>⏹ Stop</button>{" "}
    <label>Threshold <input type="number" step="0.05" value={thr} onChange={(e) => setThr(+e.target.value)} /></label>{" "}
    <button onClick={() => post("/api/autopilot/threshold", { threshold: thr })}>Apply override</button>
    <div>{PHASES.map((p, i) => <span key={p} style={{ padding: 4, margin: 2, background: live?.phase === p ? "#4caf50" : "#333", borderRadius: 4 }}>{i + 1}. {p}</span>)}</div>
    <h3>Decision log (live)</h3>
    <pre data-testid="decision-log">{(live?.recent || []).map((h) => `${new Date(h.ts * 1000).toISOString().slice(11, 19)} ${h.event} ${JSON.stringify(h.thresholds || h.savings_multiple || h.decision || "")}`).join("\n")}</pre>
  </section>);
}

/** 📊 Live Metrics: AUROC per failure type, cost time-series, confidence histogram + threshold marker. */
export function Metrics({ live }) {
  const m = live?.metrics || {};
  const auc = Object.entries(m.auroc_per_type || {});
  const series = (m.cost?.series || []).map((s) => s.savings_multiple);
  const hist = m.confidence_hist || [];
  return (<section>
    <h2>Live Metrics</h2>
    <h3>Graph 1 — AUROC per failure type</h3>
    <Plot data={[{ type: "bar", x: auc.map((a) => a[0]), y: auc.map((a) => a[1]) }]} layout={{ yaxis: { range: [0, 1], title: "AUROC" } }} />
    <h3>Graph 2 — Cost savings (tokens avoided multiple)</h3>
    <Plot data={[{ type: "scatter", mode: "lines+markers", x: series.map((_, i) => i), y: series }]} layout={{ yaxis: { title: "x savings" } }} />
    <h3>Graph 3 — Confidence distribution + auto-tuned threshold</h3>
    <Plot data={[{ type: "bar", x: hist.map((_, i) => (i / 20).toFixed(2)), y: hist }]}
      layout={{ shapes: m.threshold_marker != null ? [{ type: "line", x0: String(Math.floor(m.threshold_marker * 20) / 20), x1: String(Math.floor(m.threshold_marker * 20) / 20), y0: 0, y1: Math.max(...hist, 1), line: { color: "red", width: 2 } }] : [] }} />
    <p>AUROC overall: {m.calibration?.auroc ?? "—"} · FN rate: {m.calibration?.fn_rate ?? "—"} · Savings: {m.cost?.savings_multiple ?? "—"}x</p>
  </section>);
}

/** 🚦 CI/CD Gate Monitor. */
export function Gate({ live }) {
  const [g, setG] = useState({});
  useEffect(() => { fetch("/api/gate").then((r) => r.json()).then(setG); }, [live?.ts]);
  return (<section>
    <h2>CI/CD Gate Monitor</h2>
    <p>Pipeline: {live?.running ? "🟡 running" : g.blocked_reasons?.length ? "🔴 blocked" : "🟢 green"}</p>
    <ul>{(g.blocked_reasons || live?.blocked_reasons || []).map((b, i) => <li key={i}>⛔ {b}</li>)}</ul>
    <p>Cycles: {g.cycles ?? 0} · Historical pass rate: {((g.pass_rate ?? 0) * 100).toFixed(0)}%</p>
  </section>);
}

/** 🔒 Security Center. */
export function Security({ token, live }) {
  const [d, setD] = useState({ scan: {}, audit: [] });
  useEffect(() => { fetch("/api/security", { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()).then(setD).catch(() => {}); }, [token, live?.ts]);
  return (<section>
    <h2>Security Center</h2>
    <p>PII findings: {JSON.stringify(d.scan?.pii || {})}</p>
    <p>Secrets: {JSON.stringify(d.scan?.secrets || [])} · Critical: {JSON.stringify(d.scan?.critical || [])}</p>
    <h3>Audit log (sanitized)</h3>
    <pre style={{ maxHeight: 260, overflow: "auto" }}>{d.audit.slice(-30).map((a) => JSON.stringify(a)).join("\n")}</pre>
  </section>);
}

/** 📚 Docs Hub. */
export function Docs() {
  const names = ["README.md", "CONTRIBUTING.md", "SECURITY.md", "setup_guide.md", "install_guide.md", "RESULTS.md"];
  const [doc, setDoc] = useState("");
  return (<section>
    <h2>Docs Hub</h2>
    {names.map((n) => <button key={n} style={{ margin: 2 }} onClick={() => fetch(`/api/docs/${n}`).then((r) => r.json()).then((d) => setDoc(d.markdown))}>{n}</button>)}
    <pre data-testid="doc-viewer" style={{ whiteSpace: "pre-wrap", maxHeight: 480, overflow: "auto" }}>{doc}</pre>
  </section>);
}

/** ⚙️ Admin (auth required). */
export function Admin({ token }) {
  const [users, setUsers] = useState([]);
  const load = () => fetch("/api/admin/users", { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()).then(setUsers).catch(() => setUsers([]));
  useEffect(load, [token]);
  const rotate = (name, role) => fetch("/api/admin/users", { method: "POST", headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: JSON.stringify({ name, role }) }).then(load);
  return (<section>
    <h2>Admin</h2>
    <table><thead><tr><th>User</th><th>Role</th><th>Rotate secret</th></tr></thead>
      <tbody>{users.map((u) => <tr key={u.name}><td>{u.name}</td><td>{u.role}</td><td><button onClick={() => rotate(u.name, u.role)}>↻</button></td></tr>)}</tbody></table>
  </section>);
}
