#!/usr/bin/env python3
"""
BrandTrust Evaluation Scoreboard (Improvement 2)
------------------------------------------------
Runs a labelled test set through Layers A/B/C and reports precision / recall.

Usage:
    python scripts/run_scoreboard.py \
        --test-set data/eval_set_v2.json \
        --out results/scoreboard.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.rules import run_rule_layer
from engine.claims import run_claim_layer
from engine.drift import run_drift_layer


DEFAULT_CONSTITUTION = {
    "rules": [
        {
            "id": "no_guarantee",
            "type": "banned_term",
            "terms": ["guaranteed", "guarantee"],
            "explanation": "Absolute guarantee language is not permitted.",
        }
    ]
}

DEFAULT_LEDGER = [
    {
        "id": "fact_001",
        "statement": "Up to 60% savings observed in a pilot of 12 customers",
        "value": "60",
        "population": "pilot of 12 customers",
        "qualifiers": ["up to"],
    },
    {
        "id": "fact_002",
        "statement": "Average 35% reduction in processing time for enterprise users",
        "value": "35",
        "population": "enterprise users",
    },
]


def evaluate_item(
    item: Dict[str, Any],
    constitution: Dict[str, Any],
    ledger: List[Dict[str, Any]],
) -> Dict[str, Any]:
    text = item["text"]
    findings: List[Dict[str, Any]] = []

    findings.extend(run_rule_layer(text, constitution))
    findings.extend(run_claim_layer(text, ledger))
    findings.extend(run_drift_layer(text, ledger))

    predicted_layers = {f.get("layer") for f in findings if f.get("layer")}
    expected = item.get("expected_layer")
    hit = expected in predicted_layers if expected else None

    return {
        "id": item["id"],
        "expected_layer": expected,
        "predicted_layers": sorted(predicted_layers),
        "hit": hit,
        "findings_count": len(findings),
        "findings": findings,
    }


def run_scoreboard(
    test_set: List[Dict[str, Any]],
    constitution: Dict[str, Any] | None = None,
    ledger: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    constitution = constitution or DEFAULT_CONSTITUTION
    ledger = ledger or DEFAULT_LEDGER

    results = [evaluate_item(item, constitution, ledger) for item in test_set]

    layers = ["rules", "claims", "drift"]
    metrics: Dict[str, Dict[str, float]] = {}

    for layer in layers:
        relevant = [r for r in results if r["expected_layer"] == layer]
        if not relevant:
            metrics[layer] = {"precision": 0.0, "recall": 0.0, "support": 0}
            continue

        true_positives = sum(1 for r in relevant if r["hit"])
        predicted_as_layer = [r for r in results if layer in r["predicted_layers"]]
        precision = true_positives / len(predicted_as_layer) if predicted_as_layer else 0.0
        recall = true_positives / len(relevant) if relevant else 0.0

        metrics[layer] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "support": len(relevant),
            "true_positives": true_positives,
        }

    overall_hits = sum(1 for r in results if r["hit"])
    overall_recall = overall_hits / len(results) if results else 0.0

    return {
        "total_items": len(results),
        "overall_recall": round(overall_recall, 3),
        "metrics_by_layer": metrics,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="BrandTrust evaluation scoreboard")
    parser.add_argument("--test-set", type=Path, default=Path("data/eval_set_v2.json"))
    parser.add_argument("--out", type=Path, default=Path("results/scoreboard.json"))
    parser.add_argument("--constitution", type=Path, default=None)
    parser.add_argument("--ledger", type=Path, default=None)
    args = parser.parse_args()

    if not args.test_set.exists():
        print(f"Test set not found: {args.test_set}", file=sys.stderr)
        sys.exit(1)

    test_set = json.loads(args.test_set.read_text())
    constitution = json.loads(args.constitution.read_text()) if args.constitution else None
    ledger = json.loads(args.ledger.read_text()) if args.ledger else None

    scoreboard = run_scoreboard(test_set, constitution, ledger)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(scoreboard, indent=2))

    print("\n=== BrandTrust Scoreboard (Improvement 2) ===")
    print(f"Total items    : {scoreboard['total_items']}")
    print(f"Overall recall : {scoreboard['overall_recall']}")
    print("\nPer-layer metrics:")
    for layer, m in scoreboard["metrics_by_layer"].items():
        print(
            f"  {layer:8s}  precision={m['precision']:.3f}  "
            f"recall={m['recall']:.3f}  support={m['support']}"
        )
    print(f"\nFull results written to {args.out}")


if __name__ == "__main__":
    main()
