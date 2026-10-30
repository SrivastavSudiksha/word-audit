"""
Rules version inside the Passport signature.

Decision (from the proposal):
  "An old approval never covers a new version."

Therefore verify_passport() returns:
  - valid=True only when signature + content hash match
  - rules_newer=True when current guideline_version != approved version
  - The caller (UI / API) can choose to treat rules_newer as a hard fail
    or as a warning. The function itself never auto-fails on version alone;
    it reports the fact so the product can enforce the policy.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def create_passport(
    content_id: str,
    content_text: str,
    guideline_version: str,
    evidence_snapshot: Dict[str, Any],
    approver_id: str,
    ai_role: str = "none",
    self_approved: bool = False,
    linked_fact_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    payload = {
        "content_id": content_id,
        "content_hash": content_hash(content_text),
        "guideline_version": str(guideline_version),
        "evidence_snapshot": evidence_snapshot,
        "linked_fact_ids": linked_fact_ids or [],
        "approver_id": approver_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "ai_role": ai_role,
        "compliant_as_of": datetime.utcnow().isoformat() + "Z",
        "live_status": "approved",
        "self_approved": self_approved,
    }

    signing_input = _canonical_json({
        k: payload[k]
        for k in (
            "content_id",
            "content_hash",
            "guideline_version",
            "evidence_snapshot",
            "approver_id",
            "timestamp",
            "ai_role",
            "self_approved",
        )
    })
    # In production replace with real Ed25519 via PyNaCl
    payload["signature"] = hashlib.sha256(signing_input.encode("utf-8")).hexdigest()

    logger.info(
        "Passport created content=%s guideline_version=%s",
        content_id,
        guideline_version,
    )
    return payload


def verify_passport(
    passport: Dict[str, Any],
    current_content_text: str,
    current_guideline_version: str,
    *,
    fail_on_newer_rules: bool = False,
) -> Dict[str, Any]:
    """
    Verify signature + content hash.
    Always report whether rules have moved on.
    If fail_on_newer_rules=True, treat newer rules as an invalid Passport
    (strict interpretation of "old approval never covers a new version").
    """
    result = {
        "passport_id": passport.get("id") or passport.get("content_id"),
        "valid": False,
        "content_tampered": False,
        "rules_newer": False,
        "approved_under_version": passport.get("guideline_version"),
        "current_guideline_version": current_guideline_version,
        "live_status": passport.get("live_status", "unknown"),
        "message": "",
    }

    expected_hash = content_hash(current_content_text)
    if expected_hash != passport.get("content_hash"):
        result["content_tampered"] = True
        result["message"] = "Content has been modified since approval."
        return result

    signing_input = _canonical_json({
        k: passport[k]
        for k in (
            "content_id",
            "content_hash",
            "guideline_version",
            "evidence_snapshot",
            "approver_id",
            "timestamp",
            "ai_role",
            "self_approved",
        )
        if k in passport
    })
    expected_sig = hashlib.sha256(signing_input.encode("utf-8")).hexdigest()
    if expected_sig != passport.get("signature"):
        result["message"] = "Signature mismatch – Passport may be forged."
        return result

    result["valid"] = True

    approved_ver = str(passport.get("guideline_version") or "")
    current_ver = str(current_guideline_version or "")
    if current_ver and approved_ver and current_ver != approved_ver:
        result["rules_newer"] = True
        result["message"] = (
            f"Approved under guideline version '{approved_ver}'. "
            f"Current rules are '{current_ver}'."
        )
        if fail_on_newer_rules:
            result["valid"] = False
            result["message"] += " Old approval does not cover the new version."
    else:
        result["message"] = "Passport is valid and rules version matches."

    return result
