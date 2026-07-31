"""Application-layer PII field encryption at rest.

Reversible, keyed, non-deterministic (random nonce). Stdlib only — HMAC-SHA256
in counter mode as the keystream — because native crypto wheels fail to load on
this environment's very long venv path. **Production should swap this for
AES-GCM via `cryptography` or a KMS/HSM** (the interface stays the same).

- No key configured  -> no-op (plaintext), so dev/tests run without setup.
- Values carry an `enc:v1:` prefix so decrypt is safe on legacy plaintext and
  double-encryption is avoided.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from functools import lru_cache

from app.config import get_settings

_PREFIX = "enc:v1:"


class PiiCipher:
    def __init__(self, key: str | None) -> None:
        self._key = key.encode() if key else None

    @property
    def enabled(self) -> bool:
        return self._key is not None

    def _keystream(self, nonce: bytes, n: int) -> bytes:
        out, counter = b"", 0
        while len(out) < n:
            out += hmac.new(self._key, nonce + counter.to_bytes(4, "big"), hashlib.sha256).digest()
            counter += 1
        return out[:n]

    def encrypt(self, plaintext: str | None) -> str | None:
        if plaintext is None or not self._key or plaintext.startswith(_PREFIX):
            return plaintext
        data = plaintext.encode()
        nonce = os.urandom(16)
        ct = bytes(a ^ b for a, b in zip(data, self._keystream(nonce, len(data))))
        return _PREFIX + base64.b64encode(nonce + ct).decode()

    def decrypt(self, value: str | None) -> str | None:
        if value is None or not self._key or not value.startswith(_PREFIX):
            return value
        raw = base64.b64decode(value[len(_PREFIX):])
        nonce, ct = raw[:16], raw[16:]
        return bytes(a ^ b for a, b in zip(ct, self._keystream(nonce, len(ct)))).decode()


@lru_cache
def get_cipher() -> PiiCipher:
    return PiiCipher(get_settings().pii_key)
