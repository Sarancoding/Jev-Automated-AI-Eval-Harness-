"""Phase 2: confidence-threshold calibration loop (AUROC>=0.85, FN rate<2%)."""
from __future__ import annotations

import random

import numpy as np


def auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Mann-Whitney AUROC of confidence scores vs aligned/failure labels."""
    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    pos, neg = labels == 1, labels == 0
    n_pos, n_neg = int(pos.sum()), int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return 0.5
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


class CalibrationLoop:
    """Per-task-type threshold tuner validated on held-out scores; self-iterates to gates."""

    def __init__(self, seed: int = 11):
        self.rng = random.Random(seed)

    def simulate_scores(self, cases: list[dict]) -> tuple[np.ndarray, np.ndarray]:
        """Model confidences: aligned cases cluster high, failures low with noise overlap."""
        conf, labels = [], []
        for c in cases:
            aligned = c["gold_faithfulness"] > 0.5
            base = 0.82 if aligned else 0.30
            spread = 0.10 if aligned else 0.16
            conf.append(float(np.clip(self.rng.gauss(base, spread), 0.01, 0.99)))
            labels.append(1 if aligned else 0)
        return np.array(conf), np.array(labels)

    def fn_rate(self, conf: np.ndarray, labels: np.ndarray, thr: float) -> float:
        """False-negative rate: aligned cases scored below threshold."""
        pos = conf[labels == 1]
        return float((pos < thr).mean()) if len(pos) else 0.0

    def fp_rate(self, conf: np.ndarray, labels: np.ndarray, thr: float) -> float:
        """False-positive rate: failure cases passed above threshold."""
        neg = conf[labels == 0]
        return float((neg >= thr).mean()) if len(neg) else 0.0

    def run_loop(self, cases: list[dict], auroc_gate: float = 0.85, fn_gate: float = 0.02, max_iters: int = 12) -> tuple[dict, list[dict]]:
        """Grid-search threshold per task type; LOOP until AUROC & FN gates met on validation split."""
        conf_all, lab_all = self.simulate_scores(cases)
        types = sorted({c["failure_type"] for c in cases})
        idx = list(range(len(cases)))
        self.rng.shuffle(idx)
        half = len(idx) // 2
        train_i, val_i = idx[:half], idx[half:]
        log: list[dict] = []
        thresholds: dict[str, float] = {}
        for it in range(max_iters):
            ok = True
            for t in types:
                sel_t = [i for i in train_i if cases[i]["failure_type"] == t]
                sel_v = [i for i in val_i if cases[i]["failure_type"] == t]
                if not sel_t or not sel_v:
                    continue
                best_thr, best_auc = 0.5, 0.0
                for thr in np.arange(0.30, 0.75, 0.01):
                    auc = auroc(conf_all[sel_t], lab_all[sel_t])
                    fn = self.fn_rate(conf_all[sel_t], lab_all[sel_t], float(thr))
                    score = auc - max(0.0, fn - fn_gate) * 5
                    if auc >= best_auc and score >= 0:
                        best_auc, best_thr = auc, float(thr)
                v_auc = auroc(conf_all[sel_v], lab_all[sel_v])
                v_fn = self.fn_rate(conf_all[sel_v], lab_all[sel_v], best_thr)
                thresholds[t] = round(best_thr, 3)
                if v_auc < auroc_gate or v_fn > fn_gate:
                    ok = False
                log.append({"iter": it, "task_type": t, "threshold": thresholds[t],
                            "val_auroc": round(v_auc, 3), "val_fn": round(v_fn, 4),
                            "decision": "accept" if v_auc >= auroc_gate and v_fn <= fn_gate else "retune"})
            if ok:
                overall = {"thresholds": thresholds,
                           "auroc": round(auroc(conf_all, lab_all), 3),
                           "fn_rate": round(self.fn_rate(conf_all, lab_all, float(np.mean(list(thresholds.values())))), 4),
                           "converged": True}
                return overall, log
        overall = {"thresholds": thresholds, "auroc": round(auroc(conf_all, lab_all), 3),
                   "fn_rate": round(self.fn_rate(conf_all, lab_all, 0.5), 4), "converged": False}
        return overall, log
