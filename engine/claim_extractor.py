"""
Deterministic claim extraction (regex-based).
No external LLM dependency. Path is always logged as "regex".
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtractedClaim(BaseModel):
    subject: str = ""
    metric: str = ""
    value: Optional[str] = None
    comparator: Optional[str] = None
    population: Optional[str] = None
    conditions: Optional[str] = None
    timeframe: Optional[str] = None
    qualifiers: List[str] = Field(default_factory=list)
    raw_text: str
    extraction_path: str = "regex"


CLAIM_PATTERNS = [
    # "up to 60% savings", "guaranteed 40% reduction"
    re.compile(
        r"(?P<qualifiers>up to|as much as|guaranteed|over|more than|at least|"
        r"approximately|about|nearly)?\s*"
        r"(?P<value>\d+(?:\.\d+)?)\s*%?\s*"
        r"(?P<metric>savings?|reduction|increase|growth|improvement|accuracy|"
        r"faster|cheaper|better)",
        re.IGNORECASE,
    ),
    # "saves 2 hours per week for every customer"
    re.compile(
        r"(?P<metric>saves?|reduces?|cuts?|improves?)\s+"
        r"(?P<value>\d+(?:\.\d+)?)\s*"
        r"(?P<unit>hours?|days?|minutes?|%|percent)?\s*"
        r"(?:per\s+)?(?P<population>customer|user|employee|team|week|month|year)?",
        re.IGNORECASE,
    ),
    # "100% of customers" / "every single user"
    re.compile(
        r"(?P<value>100%|all|every|always)\s+"
        r"(?:of\s+)?(?P<population>customers?|users?|clients?|teams?)",
        re.IGNORECASE,
    ),
]


def extract_claims(text: str) -> List[ExtractedClaim]:
    """Extract claims using deterministic regex patterns. Always logs path."""
    claims: List[ExtractedClaim] = []
    seen = set()

    for pattern in CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0).strip()
            key = raw.lower()
            if key in seen:
                continue
            seen.add(key)

            groups = match.groupdict()
            claims.append(
                ExtractedClaim(
                    subject="",
                    metric=(groups.get("metric") or "").strip(),
                    value=groups.get("value"),
                    comparator=None,
                    population=groups.get("population"),
                    conditions=None,
                    timeframe=None,
                    qualifiers=[q for q in [groups.get("qualifiers")] if q],
                    raw_text=raw,
                    extraction_path="regex",
                )
            )

    logger.info("Claim extraction path=regex count=%d", len(claims))
    return claims
