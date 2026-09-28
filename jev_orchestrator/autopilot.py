"""Jev Autopilot: state machine executing eval Phases 1-7 with self-triggered loops."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .calibration import CalibrationLoop, auroc
from .data_gen import DataGenLoop
from .github_pusher import GitHubPusher
from .security_scanner import SecurityLayer

import numpy as np

STATE_FILE = Path("webapp/backend/state/metrics.json")
AUDIT_FILE = Path("webapp/backend/state/audit.log")
PHASES = ["data_gen", "calibration", "eval_execution", "cost_optimization", "security_scan", "dashboard_sync", "github_deploy"]


class JevAutopilot:
    """Central orchestrator — runs all project phases autonomously and publishes live state."""

    def __init__(self, root: str | Path = "."):
        self.root = Path(root)
        self.security = SecurityLayer(root)
        self.state: dict = {"running": False, "phase": None, "phase_index": -1, "decisions": [],
                            "metrics": {}, "history": [], "blocked_reasons": [], "repo_url": "",
                            "threshold_override": None, "updated_at": 0.0}
        self._lock = threading.Lock()
        self._stop = threading.Event()

    # ---- live-state plumbing (Phase 6) ----
    def _publish(self, event: str, payload: dict | None = None) -> None:
        """Update in-memory + on-disk state so the web dashboard auto-refreshes."""
        with self._lock:
            self.state["updated_at"] = time.time()
            self.state["history"].append({"ts": time.time(), "event": event, **(payload or {})})
            self.state["history"] = self.state["history"][-500:]
            snapshot = SecurityLayer._scrub(self.state)
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps(snapshot, indent=1))
        self.security.audit_log(AUDIT_FILE, {"event": event, **(payload or {})})

    def start_async(self, domain_docs: str, threshold: float = 0.9) -> None:
        """Launch full cycle in a background thread (UI 'Start Autopilot')."""
        if self.state["running"]:
            return
        self._stop.clear()
        threading.Thread(target=self.run_full_cycle, args=(domain_docs, threshold), daemon=True).start()

    def stop(self) -> None:
        """Request loop interruption at next phase boundary."""
        self._stop.set()
        self._publish("autopilot_stop_requested")

    def set_threshold(self, thr: float | None) -> None:
        """Operator override for gate threshold, consumed by calibration/eval."""
        with self._lock:
            self.state["threshold_override"] = thr
        self._publish("threshold_override", {"threshold": thr})

    def _phase(self, i: int, name: str) -> bool:
        """Advance state machine; returns False if stop requested."""
        if self._stop.is_set():
            self._publish("autopilot_stopped", {"phase": name})
            with self._lock:
                self.state["running"] = False
            return False
        with self._lock:
            self.state.update(running=True, phase=name, phase_index=i)
        self._publish("phase_start", {"phase": name})
        return True

    # ---- full autonomous cycle ----
    def run_full_cycle(self, domain_docs: str, threshold: float = 0.9) -> dict:
        """Executes Phases 1-7 autonomously. Returns {auroc, cost_savings, blocked_reasons, repo_url}."""
        t0 = time.time()
        with self._lock:
            self.state.update(running=True, blocked_reasons=[], decisions=[])
        docs = self.security.sanitize(domain_docs)
        out = {"auroc": 0.0, "cost_savings": 0.0, "blocked_reasons": [], "repo_url": ""}

        # Phase 1 — data gen loop
        if not self._phase(0, PHASES[0]):
            return out
        cases, dg_log = DataGenLoop().run_loop(docs)
        out["blocked_reasons"] += [f"data_gen gate unmet: {dg_log[-1]}" for dg_log_ in [dg_log] if dg_log_[-1]["decision"] != "stop"]
        self._publish("data_gen_done", {"n_cases": len(cases), "coverage": dg_log[-1]["coverage"], "diversity": dg_log[-1]["diversity"]})

        # Phase 2 — calibration loop
        if not self._phase(1, PHASES[1]):
            return out
        cal, cal_log = CalibrationLoop().run_loop(cases)
        thr = self.state.get("threshold_override") or threshold
        out["auroc"] = cal["auroc"]
        if cal["auroc"] < 0.85:
            out["blocked_reasons"].append(f"AUROC {cal['auroc']} < 0.85")
        if cal["fn_rate"] > 0.02:
            out["blocked_reasons"].append(f"FN rate {cal['fn_rate']} > 2%")
        self._publish("calibration_done", cal)

        # Phase 3 — eval execution loop (Ragas/TruLens-style metrics via eval_harness)
        if not self._phase(2, PHASES[2]):
            return out
        from eval_harness.metrics import EvalRunner
        ev = EvalRunner(threshold=float(np.mean(list(cal["thresholds"].values())) if cal["thresholds"] else thr)).run(cases)
        if ev["composite"] < 90 or ev["pii_detected"] or ev["cve_detected"]:
            out["blocked_reasons"].append(f"eval gate: composite={ev['composite']}, pii={ev['pii_detected']}, cve={ev['cve_detected']}")
        self._publish("eval_done", ev)

        # Phase 4 — cost optimization loop
        if not self._phase(3, PHASES[3]):
            return out
        from eval_harness.metrics import CostModel
        cost = CostModel(baseline_tokens=ev["total_tokens"]).optimize(ev["routed"])
        out["cost_savings"] = cost["savings_multiple"]
        if cost["savings_multiple"] < 63:
            out["blocked_reasons"].append(f"cost savings {cost['savings_multiple']}x < 63x")
        self._publish("cost_done", cost)

        # Phase 5 — security scan loop
        if not self._phase(4, PHASES[4]):
            return out
        sec = self.security.scan_repo()
        if sec["critical"]:
            out["blocked_reasons"].append(f"security critical: {sec['critical']}")
        self._publish("security_done", sec)

        # Phase 6 — dashboard sync (metrics snapshot)
        if not self._phase(5, PHASES[5]):
            return out
        per_type = {}
        conf_all, lab_all = CalibrationLoop().simulate_scores(cases)
        for t in sorted({c["failure_type"] for c in cases}):
            sel = [i for i, c in enumerate(cases) if c["failure_type"] == t]
            per_type[t] = round(auroc(conf_all[sel], lab_all[sel]), 3) if len(set(lab_all[sel].tolist())) > 1 else None
        with self._lock:
            self.state["metrics"] = {"auroc_per_type": per_type, "cost": cost, "eval": ev,
                                     "calibration": cal, "security": sec,
                                     "confidence_hist": np.histogram(conf_all, bins=20, range=(0, 1))[0].tolist(),
                                     "threshold_marker": float(np.mean(list(cal["thresholds"].values()) or [thr]))}
        self._publish("dashboard_synced", {"auroc": out["auroc"], "cost_savings": out["cost_savings"]})

        # Phase 7 — GitHub auto-deploy (only if gates passed)
        if not self._phase(6, PHASES[6]):
            return out
        if out["blocked_reasons"]:
            self._publish("deploy_blocked", {"reasons": out["blocked_reasons"]})
        else:
            dep = GitHubPusher(root=self.root).deploy()
            out["repo_url"] = dep["repo_url"]
            self._publish("deploy_done", dep)

        with self._lock:
            self.state.update(running=False, phase="idle", phase_index=-1,
                              blocked_reasons=out["blocked_reasons"], repo_url=out["repo_url"] or self.state.get("repo_url", ""))
        out["duration_s"] = round(time.time() - t0, 2)
        self._publish("cycle_complete", {k: out[k] for k in ("auroc", "cost_savings", "duration_s")})
        return out
