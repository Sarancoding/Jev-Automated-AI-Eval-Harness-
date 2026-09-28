"""Standalone synthetic dataset generator CLI (Jev Phase 1 entry point)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jev_orchestrator.data_gen import DataGenLoop


def main() -> None:
    """Generate edge-case Q&A JSON from a docs file until coverage/diversity gates pass."""
    ap = argparse.ArgumentParser(description="Jev synthetic data generation loop")
    ap.add_argument("--docs", required=True, help="Path to domain documentation text")
    ap.add_argument("--out", default="webapp/backend/state/dataset.json")
    ap.add_argument("--coverage-gate", type=float, default=0.95)
    ap.add_argument("--diversity-gate", type=float, default=0.8)
    args = ap.parse_args()
    docs = Path(args.docs).read_text()
    cases, log = DataGenLoop().run_loop(docs, args.coverage_gate, args.diversity_gate)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"cases": cases, "loop_log": log}, indent=1))
    print(f"wrote {len(cases)} cases -> {out}; final log: {log[-1]}")


if __name__ == "__main__":
    main()
