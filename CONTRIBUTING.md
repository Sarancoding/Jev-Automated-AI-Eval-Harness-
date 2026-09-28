# Contributing — Extending Jev's Automation Rules

All behavior lives in `jev_orchestrator/`. To extend:

1. **Add a loop rule:** subclass or edit the relevant loop (`data_gen.DataGenLoop`, `calibration.CalibrationLoop`) and expose its exit criteria (e.g. `coverage >= 0.95`). Loops must be self-terminating predicates — never manual steps.
2. **Gate a new metric:** add it to `eval_harness/metrics.py`; `autopilot.run_full_cycle` reads blockers from the returned dict and publishes `blocked_reasons` to the dashboard automatically.
3. **Surface it in the UI:** push the value into `self.state["metrics"]` via `_publish()`; then render it in `webapp/frontend/src/components/views.jsx` (Metrics view for graphs, Gate view for blockers).
4. **Security rules:** new scanners plug into `security_scanner.SecurityLayer.scan_all()`; findings flow to the Security Center and audit log with no code changes elsewhere.
5. **Commits:** conventional commits only (`feat:`/`fix:`/`docs:`). Tests in `tests/` must pass (`pytest tests/test_autopilot.py`). PRs are reviewed by the CI/CD gate monitor — a red gate blocks merge just like a red autopilot cycle blocks deploy.
