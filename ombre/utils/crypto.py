"""
Ombre Cryptography Utilities
============================
Encryption, hashing, and key generation utilities.
All operations are local — no external calls.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from typing import Any, Optional


def generate_request_id() -> str:
    """Generate a cryptographically secure unique request ID."""
    timestamp = int(time.time() * 1000)
    random_part = secrets.token_hex(8)
    return f"omb_{timestamp}_{random_part}"


def generate_session_id() -> str:
    """Generate a cryptographically secure session ID."""
    return f"sess_{secrets.token_urlsafe(16)}"


def hash_string(text: str, algorithm: str = "sha256") -> str:
    """Hash a string using the specified algorithm."""
    h = hashlib.new(algorithm)
    h.update(text.encode("utf-8"))
    return h.hexdigest()


def hash_for_cache(text: str) -> str:
    """Create a cache key hash from text."""
    normalized = " ".join(text.lower().strip().split())
    return hashlib.sha256(normalized.encode()).hexdigest()


def encrypt_data(data: Any) -> str:
    """
    Encrypt data for storage.
    Uses simple XOR with a machine-specific key for local storage.
    For production, configure an external KMS.
    """
    try:
        serialized = json.dumps(data)
        # Use machine-specific entropy as the key
        machine_key = _get_machine_key()
        encrypted = _xor_encrypt(serialized, machine_key)
        return base64.b64encode(encrypted.encode()).decode()
    except Exception:
        # If encryption fails, return as-is (logged as warning in calling code)
        return json.dumps(data)


def decrypt_data(encrypted: Any) -> Any:
    """Decrypt data from storage."""
    try:
        if isinstance(encrypted, (dict, list)):
            return encrypted  # Already decrypted (legacy format)
        decoded = base64.b64decode(encrypted.encode()).decode()
        machine_key = _get_machine_key()
        decrypted = _xor_encrypt(decoded, machine_key)  # XOR is its own inverse
        return json.loads(decrypted)
    except Exception:
        # Return as-is if decryption fails (may be unencrypted legacy data)
        try:
            return json.loads(encrypted)
        except Exception:
            return encrypted


def _get_machine_key() -> str:
    """Get or create a machine-specific encryption key."""
    key_path = os.path.expanduser("~/.ombre_key")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()
    # Generate new key
    key = secrets.token_hex(32)
    with open(key_path, "w") as f:
        f.write(key)
    os.chmod(key_path, 0o600)  # Owner read-only
    return key


def _xor_encrypt(text: str, key: str) -> str:
    """Simple XOR encryption. Key is repeated as needed."""
    result = []
    for i, char in enumerate(text):
        key_char = key[i % len(key)]
        result.append(chr(ord(char) ^ ord(key_char)))
    return "".join(result)


def create_hmac(data: str, key: str) -> str:
    """Create an HMAC for data integrity verification."""
    import hmac as hmac_module
    mac = hmac_module.new(
        key.encode(),
        data.encode(),
        hashlib.sha256,
    )
    return mac.hexdigest()


def verify_hmac(data: str, key: str, expected_mac: str) -> bool:
    """Verify an HMAC."""
    import hmac as hmac_module
    computed = create_hmac(data, key)
    return hmac_module.compare_digest(computed, expected_mac)


def secure_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks."""
    import hmac as hmac_module
    return hmac_module.compare_digest(
        a.encode("utf-8"),
        b.encode("utf-8"),
    )
