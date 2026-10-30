"""
Layer B – Match extracted claims against the Claim Ledger.
Statuses: Verified | Contradicted | Unsupported | Uncertain
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from .claim_extractor import ExtractedClaim, extract_claims

logger = logging.getLogger(__name__)


def run_claim_layer(text: str, ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    claims = extract_claims(text)
    findings: List[Dict[str, Any]] = []

    for claim in claims:
        match = _best_ledger_match(claim, ledger)
        finding = _build_finding(claim, match)
        if finding:
            findings.append(finding)

    return findings


def _best_ledger_match(
    claim: ExtractedClaim,
    ledger: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not ledger:
        return None

    claim_text = (claim.raw_text or "").lower()
    claim_value = _to_float(claim.value)

    best = None
    best_score = 0.0

    for fact in ledger:
        score = 0.0
        fact_text = (fact.get("statement") or fact.get("text") or "").lower()
        fact_value = _to_float(fact.get("value"))

        claim_tokens = set(re.findall(r"\w+", claim_text))
        fact_tokens = set(re.findall(r"\w+", fact_text))
        if claim_tokens and fact_tokens:
            overlap = len(claim_tokens & fact_tokens) / max(len(claim_tokens), 1)
            score += overlap * 0.6

        if claim_value is not None and fact_value is not None:
            if claim_value == fact_value:
                score += 0.4
            elif abs(claim_value - fact_value) / max(abs(fact_value), 1) < 0.15:
                score += 0.2

        if score > best_score:
            best_score = score
            best = {**fact, "_match_score": score}

    if best and best_score >= 0.35:
        return best
    return None


def _build_finding(
    claim: ExtractedClaim,
    match: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    base = {
        "layer": "claims",
        "detection_method": "Deterministic",
        "raw_text": claim.raw_text,
        "claim": claim.model_dump(),
        "extraction_path": claim.extraction_path,
    }

    if match is None:
        return {
            **base,
            "review_status": "Unsupported",
            "explanation": "No approved evidence found in the Claim Ledger for this statement.",
            "rule_or_fact_ref": None,
            "match_score": 0.0,
        }

    score = match.get("_match_score", 0.0)
    fact_id = match.get("id") or match.get("canonical_id")
    fact_statement = match.get("statement") or match.get("text") or ""

    claim_val = _to_float(claim.value)
    fact_val = _to_float(match.get("value"))
    contradicted = False
    if claim_val is not None and fact_val is not None:
        if abs(claim_val - fact_val) / max(abs(fact_val), 1) > 0.25:
            contradicted = True

    if contradicted:
        status = "Contradicted"
        explanation = (
            f"Claim value conflicts with approved fact (ledger value ≈ {fact_val}). "
            f"Source: {fact_statement[:120]}"
        )
    elif score >= 0.7:
        status = "Verified"
        explanation = f"Matches approved fact: {fact_statement[:120]}"
    else:
        status = "Uncertain"
        explanation = (
            f"Partial match (score={score:.2f}) with approved fact. "
            f"Manual verification recommended. Source: {fact_statement[:80]}"
        )

    return {
        **base,
        "review_status": status,
        "explanation": explanation,
        "rule_or_fact_ref": fact_id,
        "match_score": score,
        "ledger_fact": {
            "id": fact_id,
            "statement": fact_statement,
            "value": match.get("value"),
            "expiry": match.get("expiry"),
        },
    }


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(re.sub(r"[^\d.]", "", str(val)))
    except (ValueError, TypeError):
        return None
