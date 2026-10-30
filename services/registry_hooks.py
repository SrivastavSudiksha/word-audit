"""
Hooks to run when rules change.

1. Linter on rule draft / approve
2. Flag content when a new constitution version is released
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def on_rule_drafted_or_approved(
    rule: Dict[str, Any],
    live_rules: List[Dict[str, Any]],
    linter_run_fn,
) -> Dict[str, Any]:
    """
    Call this from registry.approve_rule (and optionally from draft).

    Runs the Linter and returns warnings. The caller decides whether to
    block the approval or only surface a warning.
    """
    try:
        findings = linter_run_fn(live_rules + [rule])
    except Exception as exc:
        logger.exception("Linter failed on rule change")
        return {
            "ok": False,
            "error": str(exc),
            "findings": [],
            "block_approval": False,
        }

    conflicts = [
        f for f in findings
        if f.get("type") in ("contradiction", "conflict", "explicit_conflict")
    ]
    ambiguities = [
        f for f in findings
        if f.get("type") in ("ambiguity", "vague", "interpretation_disagreement")
    ]

    block = len(conflicts) > 0  # hard block only on clear contradictions

    return {
        "ok": True,
        "findings": findings,
        "conflict_count": len(conflicts),
        "ambiguity_count": len(ambiguities),
        "block_approval": block,
        "message": (
            f"Found {len(conflicts)} conflict(s) and {len(ambiguities)} ambiguity(ies). "
            + ("Approval blocked." if block else "Proceed with caution.")
        ),
    }


def on_constitution_released(
    new_version: str,
    previous_version: str,
    content_items: List[Dict[str, Any]],
    passports: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Call from registry.release_constitution after a new version is published.

    Marks every approved content item (and its Passport) that was checked
    under an older version so it can be re-reviewed.

    Does NOT invalidate the Passport signature; it only sets live_status
    and a human-readable notice.
    """
    flagged_content: List[str] = []
    flagged_passports: List[str] = []

    notice = (
        f"Checked under {previous_version}, rules now {new_version}"
    )

    for item in content_items:
        item_ver = str(item.get("guideline_version") or item.get("checked_under") or "")
        if item_ver and item_ver != str(new_version):
            if item.get("live_status") in ("approved", "published", None):
                item["live_status"] = "needs_re_review"
                item["flag_reason"] = "rules_version_changed"
                item["rules_notice"] = notice
                flagged_content.append(str(item.get("id", "unknown")))

    for passport in passports:
        pp_ver = str(passport.get("guideline_version") or "")
        if pp_ver and pp_ver != str(new_version):
            if passport.get("live_status") in ("approved", None):
                passport["live_status"] = "needs_re_review"
                passport["flag_reason"] = "rules_version_changed"
                passport["rules_notice"] = notice
                flagged_passports.append(str(passport.get("id", "unknown")))

    summary = {
        "new_version": new_version,
        "previous_version": previous_version,
        "flagged_content_count": len(flagged_content),
        "flagged_passport_count": len(flagged_passports),
        "flagged_content_ids": flagged_content,
        "flagged_passport_ids": flagged_passports,
        "notice": notice,
    }
    logger.info(
        "Constitution %s → %s: flagged %d content + %d passports",
        previous_version,
        new_version,
        summary["flagged_content_count"],
        summary["flagged_passport_count"],
    )
    return summary
