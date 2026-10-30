"""
Layer A – Deterministic rule checks from Brand Constitution.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List


def run_rule_layer(text: str, constitution: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    rules = constitution.get("rules") or []

    for rule in rules:
        rule_type = rule.get("type", "")
        rule_id = rule.get("id", "unknown")
        explanation = rule.get("explanation", "Rule violation")

        if rule_type == "banned_term":
            for term in rule.get("terms") or []:
                if re.search(rf"\b{re.escape(term)}\b", text, re.I):
                    findings.append({
                        "layer": "rules",
                        "detection_method": "Deterministic",
                        "review_status": "Rule violation",
                        "raw_text": term,
                        "explanation": explanation,
                        "rule_or_fact_ref": rule_id,
                    })

        elif rule_type == "required_term":
            for term in rule.get("terms") or []:
                if not re.search(rf"\b{re.escape(term)}\b", text, re.I):
                    findings.append({
                        "layer": "rules",
                        "detection_method": "Deterministic",
                        "review_status": "Rule violation",
                        "raw_text": f"(missing) {term}",
                        "explanation": f"Required term '{term}' not found. {explanation}",
                        "rule_or_fact_ref": rule_id,
                    })

        elif rule_type == "tone":
            pattern = rule.get("pattern")
            if pattern and re.search(pattern, text, re.I):
                findings.append({
                    "layer": "rules",
                    "detection_method": "Deterministic",
                    "review_status": "Rule violation",
                    "raw_text": pattern,
                    "explanation": explanation,
                    "rule_or_fact_ref": rule_id,
                })

    # Built-in safety net
    if re.search(r"\bguaranteed\b", text, re.I):
        already = any(f.get("raw_text", "").lower() == "guaranteed" for f in findings)
        if not already:
            findings.append({
                "layer": "rules",
                "detection_method": "Deterministic",
                "review_status": "Rule violation",
                "raw_text": "guaranteed",
                "explanation": "Absolute guarantee language is not permitted without explicit approval.",
                "rule_or_fact_ref": "builtin_no_guarantee",
            })

    return findings
