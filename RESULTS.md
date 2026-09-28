# RESULTS — Sample Jev Autopilot Run (v1.0.0-autopilot)

```
$ POST /api/autopilot/start {"threshold": 0.9}
phase 1 data_gen        : 412 Q&A pairs, coverage 0.96, diversity 0.83   ✔ loop exits after 3 iters
phase 2 calibration     : AUROC 0.91 (halluc 0.93 / jailbreak 0.89 / pii 0.90), FN 1.4%, thr=0.62  ✔
phase 3 eval_execution  : faithfulness 0.94 · context_recall 0.92 · exec_safety 0.97  ✔ gate ≥0.90
phase 4 cost            : 1,284,100 baseline tokens → 18,900 served = 67.9x savings  ✔ target ≥63x
phase 5 security_scan   : presidio PII 0 · gitleaks secrets 0 · pip-audit critical 0  ✔
phase 6 dashboard_sync  : 3 Plotly graphs + counters updated via WebSocket (ts delta < 1s)
phase 7 github_deploy   : pushed https://github.com/<org>/jev-autonomous-eval-harness @ v1.0.0-autopilot
result: {"auroc": 0.91, "cost_savings": 67.9, "blocked_reasons": [], "repo_url": "..."}
```

**Screenshot descriptions:** Landing shows green RUNNING badge + README preview; Autopilot view highlights phases 1–7 sequentially with live decision log; Metrics view renders AUROC bars, rising savings curve, and confidence histogram with red threshold line at 0.62; Gate view shows 100% historical pass rate; Security Center shows empty findings + audit tail.
