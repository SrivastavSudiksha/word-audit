"""
Automatic expiry sweep + impact helpers.

Call sweep_expired() on startup and from a daily cron / background task.
Also call on_ledger_edit() after every successful PATCH /ledger/{id}.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def is_expired(fact: Dict[str, Any], today: Optional[date] = None) -> bool:
    today = today or date.today()
    expiry_raw = fact.get("expiry") or fact.get("expires_at")
    if not expiry_raw:
        return False
    try:
        if isinstance(expiry_raw, date):
            expiry = expiry_raw
        elif isinstance(expiry_raw, datetime):
            expiry = expiry_raw.date()
        else:
            expiry = date.fromisoformat(str(expiry_raw)[:10])
        return expiry <= today
    except (ValueError, TypeError):
        return False


def sweep_expired(
    ledger: List[Dict[str, Any]],
    content_items: List[Dict[str, Any]],
    passports: List[Dict[str, Any]],
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Find all expired facts and set live_status='needs_re_review'
    on every linked content item and Passport.
    """
    today = today or date.today()
    expired_facts = [f for f in ledger if is_expired(f, today)]
    expired_ids = {f.get("id") or f.get("canonical_id") for f in expired_facts}

    flagged_content: List[str] = []
    flagged_passports: List[str] = []

    for item in content_items:
        linked = set(item.get("linked_fact_ids") or item.get("fact_ids") or [])
        if linked & expired_ids:
            item["live_status"] = "needs_re_review"
            item["flag_reason"] = "linked_fact_expired"
            flagged_content.append(str(item.get("id", "unknown")))

    for passport in passports:
        linked = set(
            passport.get("linked_fact_ids")
            or passport.get("evidence_fact_ids")
            or []
        )
        snapshot = passport.get("evidence_snapshot") or {}
        if isinstance(snapshot, dict):
            linked |= set(snapshot.get("fact_ids") or [])
        if linked & expired_ids:
            passport["live_status"] = "needs_re_review"
            passport["flag_reason"] = "linked_fact_expired"
            flagged_passports.append(str(passport.get("id", "unknown")))

    summary = {
        "swept_at": datetime.utcnow().isoformat() + "Z",
        "expired_fact_count": len(expired_facts),
        "expired_fact_ids": list(expired_ids),
        "flagged_content_ids": flagged_content,
        "flagged_passport_ids": flagged_passports,
        "flagged_content_count": len(flagged_content),
        "flagged_passport_count": len(flagged_passports),
    }
    logger.info(
        "Expiry sweep: %d facts → %d content + %d passports flagged",
        summary["expired_fact_count"],
        summary["flagged_content_count"],
        summary["flagged_passport_count"],
    )
    return summary


def on_ledger_edit(
    fact_id: str,
    ledger: List[Dict[str, Any]],
    content_items: List[Dict[str, Any]],
    passports: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Call immediately after PATCH /ledger/{id}."""
    fact = next(
        (f for f in ledger if (f.get("id") or f.get("canonical_id")) == fact_id),
        None,
    )
    if fact is None:
        return {"error": "fact_not_found", "fact_id": fact_id}

    if not is_expired(fact):
        return {
            "fact_id": fact_id,
            "expired": False,
            "message": "Fact is not expired; no flags raised.",
        }

    return sweep_expired(
        ledger=[fact],
        content_items=content_items,
        passports=passports,
    )
