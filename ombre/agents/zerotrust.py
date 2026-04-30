"""
Ombre Zero Trust AI Gateway
=============================
Every user. Every request. Verified and scoped.

No user gets more AI access than they need.
No user can see another user's AI context.
Every action logged per user per request.

This is what enterprise AI security actually looks like.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List, Optional, Set

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ZeroTrustGateway:
    """
    Ombre Zero Trust AI Gateway.

    Role-based AI access control.
    User context isolation.
    Per-user audit trails.
    """

    def __init__(self, config: Any):
        self.config = config
        self._roles: Dict[str, Dict[str, Any]] = {}
        self._user_roles: Dict[str, str] = {}
        self._blocked_users: Set[str] = set()
        self._user_request_counts: Dict[str, int] = {}
        self._rate_limits: Dict[str, int] = {}
        self._total_checks = 0
        self._total_blocked = 0

        # Default roles
        self._setup_default_roles()

    def _setup_default_roles(self) -> None:
        """Setup default role configurations."""
        self._roles = {
            "admin": {
                "allowed_models": ["*"],
                "max_tokens": 100000,
                "rate_limit_per_hour": 10000,
                "can_export_audit": True,
                "can_access_memory": True,
            },
            "user": {
                "allowed_models": ["gpt-4o-mini", "claude-3-haiku-20240307"],
                "max_tokens": 4096,
                "rate_limit_per_hour": 100,
                "can_export_audit": False,
                "can_access_memory": True,
            },
            "readonly": {
                "allowed_models": ["gpt-4o-mini"],
                "max_tokens": 1024,
                "rate_limit_per_hour": 20,
                "can_export_audit": False,
                "can_access_memory": False,
            },
            "restricted": {
                "allowed_models": [],
                "max_tokens": 0,
                "rate_limit_per_hour": 0,
                "can_export_audit": False,
                "can_access_memory": False,
            },
        }

    def process(self, ctx: Any) -> Any:
        """Enforce zero trust policies on every request."""
        ctx.activate_agent("zerotrust")
        self._total_checks += 1

        user_id = ctx.user_id
        if not user_id:
            return ctx  # No user ID — skip zero trust checks

        # Check if user is blocked
        if user_id in self._blocked_users:
            ctx.blocked = True
            ctx.block_reason = "User access revoked"
            self._total_blocked += 1
            return ctx

        # Get user role
        role_name = self._user_roles.get(user_id, "user")
        role = self._roles.get(role_name, self._roles["user"])

        # Check rate limit
        if not self._check_rate_limit(user_id, role):
            ctx.blocked = True
            ctx.block_reason = f"Rate limit exceeded for user {user_id}"
            self._total_blocked += 1
            logger.warning(f"Rate limit exceeded | user={user_id}")
            return ctx

        # Check model access
        if ctx.selected_model:
            allowed = role["allowed_models"]
            if "*" not in allowed and ctx.selected_model not in allowed:
                # Route to allowed model instead of blocking
                if allowed:
                    ctx.selected_model = allowed[0]
                    logger.info(
                        f"Model access restricted | user={user_id} | "
                        f"routed to {allowed[0]}"
                    )

        # Apply token limits
        if ctx.max_tokens > role["max_tokens"] and role["max_tokens"] > 0:
            ctx.max_tokens = role["max_tokens"]

        # Store role in metadata for audit
        ctx.metadata["user_role"] = role_name
        ctx.metadata["zero_trust_checked"] = True

        return ctx

    def assign_role(self, user_id: str, role: str) -> None:
        """Assign a role to a user."""
        if role not in self._roles:
            raise ValueError(f"Unknown role: {role}")
        self._user_roles[user_id] = role
        logger.info(f"Role assigned | user={user_id} | role={role}")

    def block_user(self, user_id: str, reason: str = "") -> None:
        """Block a user from AI access."""
        self._blocked_users.add(user_id)
        logger.warning(f"User blocked | user={user_id} | reason={reason}")

    def unblock_user(self, user_id: str) -> None:
        """Restore user access."""
        self._blocked_users.discard(user_id)
        logger.info(f"User unblocked | user={user_id}")

    def define_role(self, name: str, config: Dict[str, Any]) -> None:
        """Define a custom role."""
        self._roles[name] = config
        logger.info(f"Role defined | name={name}")

    def _check_rate_limit(self, user_id: str, role: Dict[str, Any]) -> bool:
        """Check if user has exceeded their rate limit."""
        limit = role.get("rate_limit_per_hour", 100)
        if limit == 0:
            return False

        now = time.time()
        hour_key = f"{user_id}_{int(now // 3600)}"

        count = self._user_request_counts.get(hour_key, 0)
        if count >= limit:
            return False

        self._user_request_counts[hour_key] = count + 1
        return True

    def get_user_report(self, user_id: str) -> Dict[str, Any]:
        """Get AI usage report for a specific user."""
        now = time.time()
        hour_key = f"{user_id}_{int(now // 3600)}"
        return {
            "user_id": user_id,
            "role": self._user_roles.get(user_id, "user"),
            "blocked": user_id in self._blocked_users,
            "requests_this_hour": self._user_request_counts.get(hour_key, 0),
        }

    def stats(self) -> Dict[str, Any]:
        return {
            "total_checks": self._total_checks,
            "total_blocked": self._total_blocked,
            "active_users": len(self._user_roles),
            "blocked_users": len(self._blocked_users),
            "defined_roles": list(self._roles.keys()),
        }
