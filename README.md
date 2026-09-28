# 🤖 Jev-Automated AI Eval Harness

Jev-driven evaluation pipeline: synthetic data generation, calibration, eval execution, CI/CD gating, security scanning, live web dashboard, and autonomous GitHub deployment. **The webpage is the control room. Jev is the operator.**

## Web UI Walkthrough (7 views)
| View | What it shows |
|------|---------------|
| 🏠 Landing | System status, this README preview, repo badge, SECURITY.md summary, PDF guide links |
| 🤖 Autopilot | Start/stop automation, current phase indicator, threshold override, live decision log |
| 📊 Metrics | Graph 1: AUROC per failure type · Graph 2: cost-savings time-series · Graph 3: confidence histogram + auto-tuned threshold marker (all Plotly, WebSocket auto-refresh) |
| 🚦 Gate | CI/CD pipeline status, blocked reasons, historical pass rate |
| 🔒 Security | PII scan results, dependency CVEs, sanitized immutable audit log |
| 📚 Docs | README / CONTRIBUTING / SECURITY / setup & install guides / RESULTS |
| ⚙️ Admin | RBAC user management + secret rotation (JWT, session timeout 1h) |

Launch: `docker-compose up` → http://localhost:5173 (API on :8000). Log in as `admin` / `jev-default`, click **▶ Start Autopilot**.

## Architecture
```
Browser (React + Plotly) ──WebSocket──> FastAPI (:8000) ──> JevAutopilot (threaded state machine)
                                                        ├── DataGenLoop      (Phase 1: coverage ≥95%, diversity ≥0.8)
                                                        ├── CalibrationLoop  (Phase 2: AUROC ≥0.85, FN <2%)
                                                        ├── eval_harness     (Phase 3: Ragas/TruLens metrics, gate <90%)
                                                        ├── Cost router      (Phase 4: ≥63x token savings)
                                                        ├── SecurityLayer    (Phase 5: presidio + gitleaks + pip-audit)
                                                        ├── STATE_FILE       (Phase 6: dashboard sync every publish)
                                                        └── GitHubPusher     (Phase 7: PyGithub, scoped GITHUB_TOKEN)
```

## How Jev Automates Everything
1. **Data Gen Loop** — analyzes domain docs, emits edge-case Q&A with RLCDAIAlignBench failure injections (hallucination / jailbreak / PII leak); self-iterates until coverage/diversity thresholds met.
2. **Calibration Loop** — tunes per-task confidence thresholds; validates AUROC ≥0.85 and FN rate <2% before releasing.
3. **Eval Execution Loop** — scores Faithfulness, Context Recall, Execution Safety; blocks release if score <90% or PII/CVE detected.
4. **Cost Optimization Loop** — tracks tokens avoided vs baseline, targets ≥63x, re-routes low-risk queries to cheap models.
5. **Security Scan Loop** — presidio PII + gitleaks secrets + pip-audit CVEs on every commit; critical findings block the gate and land in the audit trail.
6. **Dashboard Sync Loop** — every state publish pushes live metrics over WebSocket to all graphs/tables/counters.
7. **GitHub Auto-Deploy Loop** — after a green cycle, commits with conventional messages, creates/updates `jev-autonomous-eval-harness`, uploads PDF guides, tags `v1.0.0-autopilot`. Zero human intervention.

PDF guides are generated from Markdown sources (`docs/setup_guide.md`, `docs/install_guide.md`) by Phase 7; conversion uses `md-to-pdf` in the GitHub Action (`.github/workflows/jev-autopilot.yml`).

Docs: [setup guide](docs/setup_guide.md) · [install guide](docs/install_guide.md) · [CONTRIBUTING.md](CONTRIBUTING.md) · [SECURITY.md](SECURITY.md) · [RESULTS.md](RESULTS.md)
