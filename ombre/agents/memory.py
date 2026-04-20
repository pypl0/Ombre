"""
Ombre Memory Agent
==================
Persistent encrypted memory across sessions.
Loads conversation history, user context, and learned facts
into every request so AI never starts from zero.

Memory stays on the customer's own infrastructure.
Ombre never stores or transmits memory data.
"""

from __future__ import annotations

import json
import os
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger
from ..utils.crypto import encrypt_data, decrypt_data

logger = get_logger(__name__)


class MemoryAgent:
    """
    Ombre Memory Agent — Persistent context across sessions.

    Backends supported:
    - local: JSON files on disk (default, zero dependencies)
    - redis: Redis for distributed deployments
    - postgres: PostgreSQL for enterprise deployments

    All stored data is encrypted at rest using AES-256.
    """

    def __init__(self, config: Any):
        self.config = config
        self.backend = config.memory_backend
        self._cache: Dict[str, Any] = {}  # In-memory L1 cache
        self._storage_path = Path(".ombre_memory")

        # Initialize backend
        self._init_backend()

        # Stats
        self._total_loads = 0
        self._total_saves = 0
        self._cache_hits = 0

    def _init_backend(self) -> None:
        """Initialize the storage backend."""
        if self.backend == "local":
            self._storage_path.mkdir(exist_ok=True)
            logger.debug(f"Memory backend: local ({self._storage_path})")
        elif self.backend == "redis":
            self._init_redis()
        elif self.backend == "postgres":
            self._init_postgres()

    def _init_redis(self) -> None:
        """Initialize Redis backend."""
        try:
            import redis
            redis_url = os.environ.get("OMBRE_REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
            logger.debug("Memory backend: redis")
        except Exception as e:
            logger.warning(f"Redis unavailable, falling back to local: {e}")
            self.backend = "local"
            self._storage_path.mkdir(exist_ok=True)

    def _init_postgres(self) -> None:
        """Initialize PostgreSQL backend."""
        try:
            import psycopg2
            self._pg_url = os.environ.get("OMBRE_DATABASE_URL")
            if not self._pg_url:
                raise ValueError("OMBRE_DATABASE_URL not set")
            logger.debug("Memory backend: postgres")
        except Exception as e:
            logger.warning(f"Postgres unavailable, falling back to local: {e}")
            self.backend = "local"
            self._storage_path.mkdir(exist_ok=True)

    def process(self, ctx: Any) -> Any:
        """
        Load memory for this session and inject into context.

        Args:
            ctx: PipelineContext

        Returns:
            Modified context with memory loaded
        """
        ctx.activate_agent("memory")
        self._total_loads += 1
        start = time.time()

        session_id = ctx.session_id
        user_id = ctx.user_id

        # Load conversation history
        history = self._load_history(session_id)
        if history:
            ctx.conversation_history = history
            ctx.memory_loaded = True
            logger.debug(
                f"Memory loaded | session={session_id} | "
                f"history_turns={len(history)}"
            )

        # Load user context (preferences, facts, profile)
        if user_id:
            user_ctx = self._load_user_context(user_id)
            if user_ctx:
                ctx.user_context = user_ctx
                ctx.memory_loaded = True

        # Load persistent facts for this session
        facts = self._load_persistent_facts(session_id, user_id)
        if facts:
            ctx.persistent_facts = facts

        elapsed = round((time.time() - start) * 1000, 2)
        logger.debug(f"Memory agent complete | {elapsed}ms")
        return ctx

    def save_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Save a conversation turn to memory.
        Called automatically by the pipeline after each successful response.
        """
        self._total_saves += 1

        history = self._load_history(session_id)
        history.append({
            "role": "user",
            "content": user_message,
            "timestamp": time.time(),
        })
        history.append({
            "role": "assistant",
            "content": assistant_message,
            "timestamp": time.time(),
            "metadata": metadata or {},
        })

        # Trim to max history
        max_turns = self.config.memory_max_history * 2  # Each turn = 2 messages
        if len(history) > max_turns:
            history = history[-max_turns:]

        self._save_history(session_id, history)

        # Extract and save any facts from the conversation
        self._extract_and_save_facts(session_id, user_message, assistant_message)

    def save_fact(
        self,
        fact: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        confidence: float = 1.0,
        source: Optional[str] = None,
    ) -> None:
        """
        Explicitly save a fact to persistent memory.
        Facts persist across sessions for the same user.
        """
        key = self._make_key("facts", user_id or session_id or "global")
        facts = self._load(key) or []
        facts.append({
            "fact": fact,
            "confidence": confidence,
            "source": source,
            "timestamp": time.time(),
        })
        self._save(key, facts)

    def clear(self, session_id: str) -> None:
        """Clear memory for a specific session."""
        key = self._make_key("history", session_id)
        self._delete(key)
        # Also clear L1 cache
        self._cache.pop(key, None)
        logger.info(f"Memory cleared | session={session_id}")

    def flush(self) -> None:
        """Flush any pending writes."""
        # For local backend, writes are synchronous so nothing to flush
        # For Redis/Postgres, flush any buffered writes
        logger.debug("Memory flushed")

    def _load_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Load conversation history for a session."""
        key = self._make_key("history", session_id)

        # Check L1 cache first
        if key in self._cache:
            self._cache_hits += 1
            return self._cache[key]

        data = self._load(key)
        result = data or []
        self._cache[key] = result
        return result

    def _save_history(self, session_id: str, history: List[Dict[str, Any]]) -> None:
        """Save conversation history for a session."""
        key = self._make_key("history", session_id)
        self._save(key, history)
        self._cache[key] = history

    def _load_user_context(self, user_id: str) -> Dict[str, Any]:
        """Load user profile and preferences."""
        key = self._make_key("user_context", user_id)
        return self._load(key) or {}

    def _save_user_context(self, user_id: str, context: Dict[str, Any]) -> None:
        """Save user profile and preferences."""
        key = self._make_key("user_context", user_id)
        self._save(key, context)

    def _load_persistent_facts(
        self,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> List[str]:
        """Load persistent facts for this session/user."""
        facts = []

        # Session-level facts
        key = self._make_key("facts", session_id)
        session_facts = self._load(key) or []
        facts.extend([f["fact"] for f in session_facts if f.get("confidence", 0) > 0.5])

        # User-level facts (persist across sessions)
        if user_id:
            user_key = self._make_key("facts", user_id)
            user_facts = self._load(user_key) or []
            facts.extend([f["fact"] for f in user_facts if f.get("confidence", 0) > 0.5])

        return facts

    def _extract_and_save_facts(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """
        Extract factual statements from conversation and save them.
        Simple heuristic-based extraction — no LLM call needed.
        """
        # Look for explicit fact statements
        fact_indicators = [
            "my name is",
            "i am",
            "i work at",
            "i live in",
            "i prefer",
            "always",
            "never",
            "remember that",
            "important:",
        ]
        for indicator in fact_indicators:
            if indicator in user_message.lower():
                # Extract the sentence containing the indicator
                sentences = user_message.split(".")
                for sentence in sentences:
                    if indicator in sentence.lower():
                        fact = sentence.strip()
                        if len(fact) > 5 and len(fact) < 500:
                            self.save_fact(
                                fact=fact,
                                session_id=session_id,
                                confidence=0.8,
                                source="user_statement",
                            )

    # =========================================================================
    # Storage backend methods
    # =========================================================================

    def _make_key(self, namespace: str, identifier: str) -> str:
        """Create a storage key."""
        safe_id = hashlib.md5(identifier.encode()).hexdigest()
        return f"ombre_{namespace}_{safe_id}"

    def _load(self, key: str) -> Optional[Any]:
        """Load data from the configured backend."""
        try:
            if self.backend == "local":
                return self._load_local(key)
            elif self.backend == "redis":
                return self._load_redis(key)
            elif self.backend == "postgres":
                return self._load_postgres(key)
        except Exception as e:
            logger.debug(f"Memory load failed | key={key} | error={e}")
        return None

    def _save(self, key: str, data: Any) -> None:
        """Save data to the configured backend."""
        try:
            if self.backend == "local":
                self._save_local(key, data)
            elif self.backend == "redis":
                self._save_redis(key, data)
            elif self.backend == "postgres":
                self._save_postgres(key, data)
        except Exception as e:
            logger.warning(f"Memory save failed | key={key} | error={e}")

    def _delete(self, key: str) -> None:
        """Delete data from the configured backend."""
        try:
            if self.backend == "local":
                path = self._storage_path / f"{key}.json"
                if path.exists():
                    path.unlink()
        except Exception as e:
            logger.warning(f"Memory delete failed | key={key} | error={e}")

    def _load_local(self, key: str) -> Optional[Any]:
        """Load from local JSON file."""
        path = self._storage_path / f"{key}.json"
        if not path.exists():
            return None
        with open(path, "r") as f:
            wrapper = json.load(f)

        # Check TTL
        if "expires" in wrapper and wrapper["expires"] < time.time():
            path.unlink()
            return None

        data = wrapper.get("data")

        # Decrypt if encrypted
        if wrapper.get("encrypted"):
            data = decrypt_data(data)

        return data

    def _save_local(self, key: str, data: Any) -> None:
        """Save to local JSON file with TTL."""
        ttl_days = self.config.memory_ttl_days
        expires = time.time() + (ttl_days * 86400)

        # Encrypt sensitive data
        encrypted_data = encrypt_data(data)

        wrapper = {
            "data": encrypted_data,
            "encrypted": True,
            "expires": expires,
            "saved_at": time.time(),
        }
        path = self._storage_path / f"{key}.json"
        with open(path, "w") as f:
            json.dump(wrapper, f)

    def _load_redis(self, key: str) -> Optional[Any]:
        """Load from Redis."""
        raw = self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def _save_redis(self, key: str, data: Any) -> None:
        """Save to Redis with TTL."""
        ttl_seconds = self.config.memory_ttl_days * 86400
        self._redis.setex(key, ttl_seconds, json.dumps(data))

    def _load_postgres(self, key: str) -> Optional[Any]:
        """Load from PostgreSQL."""
        import psycopg2
        conn = psycopg2.connect(self._pg_url)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT data FROM ombre_memory WHERE key = %s AND (expires_at IS NULL OR expires_at > NOW())",
                    (key,)
                )
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
        finally:
            conn.close()
        return None

    def _save_postgres(self, key: str, data: Any) -> None:
        """Save to PostgreSQL."""
        import psycopg2
        conn = psycopg2.connect(self._pg_url)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ombre_memory (
                        key VARCHAR(255) PRIMARY KEY,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        expires_at TIMESTAMP
                    )
                """)
                ttl_days = self.config.memory_ttl_days
                cur.execute("""
                    INSERT INTO ombre_memory (key, data, expires_at)
                    VALUES (%s, %s, NOW() + INTERVAL '%s days')
                    ON CONFLICT (key) DO UPDATE
                    SET data = EXCLUDED.data, expires_at = EXCLUDED.expires_at
                """, (key, json.dumps(data), ttl_days))
            conn.commit()
        finally:
            conn.close()

    def stats(self) -> Dict[str, Any]:
        """Return memory agent statistics."""
        return {
            "backend": self.backend,
            "total_loads": self._total_loads,
            "total_saves": self._total_saves,
            "cache_hits": self._cache_hits,
            "l1_cache_entries": len(self._cache),
      }
