"""
Self-verifying fix generation.

Each suggested rewrite is put back into the text and the full A/B/C pipeline
is re-run. The fix is marked suggestion_verified=True only when no new
findings appear.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SuggestedFix(BaseModel):
    original_text: str
    suggested_text: str
    explanation: str
    suggestion_verified: bool = False
    new_findings_count: int = 0


def generate_and_verify_fix(
    original_content: str,
    finding: Dict[str, Any],
    constitution: Dict[str, Any],
    ledger: List[Dict[str, Any]],
) -> Optional[SuggestedFix]:
    """
    1. Generate an intent-preserving rewrite.
    2. Re-run full A/B/C pipeline on the rewritten text.
    3. Only mark suggestion_verified=True if zero new findings appear.
    """
    suggested = _generate_rewrite(original_content, finding)
    if not suggested:
        return None

    new_findings = _run_full_pipeline(suggested, constitution, ledger)

    original_type = (
        finding.get("review_status")
        or finding.get("type")
        or finding.get("layer")
    )
    truly_new = [
        f for f in new_findings
        if (f.get("review_status") or f.get("type") or f.get("layer")) != original_type
    ]

    verified = len(truly_new) == 0
    logger.info("Fix verification: verified=%s new_findings=%d", verified, len(truly_new))

    return SuggestedFix(
        original_text=finding.get("raw_text") or finding.get("excerpt") or "",
        suggested_text=suggested,
        explanation=finding.get("explanation") or "Intent-preserving rewrite",
        suggestion_verified=verified,
        new_findings_count=len(truly_new),
    )


def _generate_rewrite(content: str, finding: Dict[str, Any]) -> Optional[str]:
    text = finding.get("raw_text") or finding.get("excerpt") or ""
    if not text:
        return None

    replacements = [
        (r"\bguaranteed\s+(\d+%?)", r"up to \1"),
        (r"\bwill\s+(\w+)", r"can \1"),
        (r"\balways\s+", r"typically "),
        (r"\bfor every customer\b", r"in our pilot"),
        (r"\bfor all customers\b", r"for pilot customers"),
        (r"\b100%\s+of\s+", r"a majority of "),
        (r"\bevery single\s+", r"many "),
        (r"\bnever\b", r"rarely"),
        (r"\bbest\b", r"leading"),
    ]

    new_span = text
    for pattern, repl in replacements:
        new_span = re.sub(pattern, repl, new_span, flags=re.IGNORECASE)

    if new_span.lower() == text.lower():
        if not text.lower().startswith("up to"):
            new_span = f"up to {text}"
        else:
            return None

    if text in content:
        return content.replace(text, new_span, 1)
    return new_span


def _run_full_pipeline(
    text: str,
    constitution: Dict[str, Any],
    ledger: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    from .rules import run_rule_layer
    from .claims import run_claim_layer
    from .drift import run_drift_layer

    findings: List[Dict[str, Any]] = []
    findings.extend(run_rule_layer(text, constitution))
    findings.extend(run_claim_layer(text, ledger))
    findings.extend(run_drift_layer(text, ledger))
    return findings
