"""
Layer C – Semantic Drift detection.
Detects qualifier loss, scope widening and guarantee language.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


DRIFT_PATTERNS = [
    {
        "id": "qualifier_loss",
        "pattern": re.compile(r"\b(guaranteed|always|never|100%|every single)\b", re.I),
        "explanation": (
            "Absolute language detected. Approved evidence usually contains "
            "qualifiers such as 'up to', 'in pilot', or 'typically'."
        ),
        "suggestion_hint": "Add a qualifier (e.g. 'up to', 'in our pilot') to stay faithful to the evidence.",
    },
    {
        "id": "scope_widening",
        "pattern": re.compile(
            r"\b(for every customer|for all customers|for all users|across all)\b",
            re.I,
        ),
        "explanation": (
            "Scope appears widened beyond the population present in the "
            "approved evidence (often a pilot or limited cohort)."
        ),
        "suggestion_hint": "Limit the claim to the population that was actually measured.",
    },
    {
        "id": "guarantee_language",
        "pattern": re.compile(r"\b(will deliver|will achieve|promises?|ensures?)\b", re.I),
        "explanation": (
            "Future-guarantee wording. Prefer language that reflects observed "
            "results rather than promises."
        ),
        "suggestion_hint": "Replace with observed-result language (e.g. 'customers saw', 'in the pilot we measured').",
    },
]


def run_drift_layer(text: str, ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    for rule in DRIFT_PATTERNS:
        for match in rule["pattern"].finditer(text):
            findings.append({
                "layer": "drift",
                "detection_method": "Deterministic",
                "review_status": "Needs verification",
                "raw_text": match.group(0),
                "explanation": rule["explanation"],
                "suggestion_hint": rule["suggestion_hint"],
                "rule_or_fact_ref": rule["id"],
                "drift_type": rule["id"],
            })

    return findings
