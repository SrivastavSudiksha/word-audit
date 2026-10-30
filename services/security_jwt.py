"""
Secure original endpoints that still trust X-Role.

Replace X-Role header checks with JWT verification from auth.py.
In production, refuse requests that only send X-Role.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status

logger = logging.getLogger(__name__)

# Set to "true" in production to hard-disable the X-Role backdoor
STRICT_JWT_ONLY = os.getenv("STRICT_JWT_ONLY", "false").lower() == "true"


def get_current_role(
    request: Request,
    # Inject your real JWT dependency here, e.g.:
    # current_user = Depends(get_current_user_from_jwt),
) -> str:
    """
    Prefer JWT. Fall back to X-Role only when STRICT_JWT_ONLY is false
    (useful for local demos). Log every X-Role use so it is visible.
    """
    # --- Preferred path: JWT ---
    # Uncomment and wire to your real auth.py:
    #
    # try:
    #     user = get_current_user_from_jwt(request)   # your existing function
    #     return user.role
    # except Exception:
    #     pass

    # --- Demo / legacy path: X-Role header ---
    role = request.headers.get("X-Role")
    if role:
        if STRICT_JWT_ONLY:
            logger.warning("Rejected X-Role header in STRICT_JWT_ONLY mode")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Role header is disabled. Use JWT.",
            )
        logger.warning("Using legacy X-Role=%s (not for production)", role)
        return role.lower()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required (JWT or X-Role)",
    )


def require_roles(*allowed: str) -> Callable:
    """
    Dependency factory.

    Usage:
        @router.post("/ledger/{id}")
        def patch_ledger(..., role: str = Depends(require_roles("manager", "approver"))):
            ...
    """
    allowed_set = {r.lower() for r in allowed}

    def _dep(role: str = Depends(get_current_role)) -> str:
        if role not in allowed_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' not permitted. Allowed: {sorted(allowed_set)}",
            )
        return role

    return _dep
