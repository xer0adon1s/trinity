"""Hash-shaped stuckness (docs/FEATURES_BACKLOG.md, originally
Trinity_suggestions.md 2.5).

Local shape classifier. No network. Not a replacement for hashid;
enough to unstick "I found a long hex string, now what?"
"""
from __future__ import annotations

import re

from pydantic import BaseModel

_BCRYPT = re.compile(r"^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$")
_JWT = re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_HEX = re.compile(r"^[A-Fa-f0-9]+$")
_MD5CRYPT = re.compile(r"^\$1\$[./A-Za-z0-9]{1,8}\$[./A-Za-z0-9]{22}$")
_SHA512CRYPT = re.compile(r"^\$6\$")


class HashGuess(BaseModel):
    label: str
    next_step: str
    confidence: str  # 'high' | 'medium' | 'low'


def classify_hash(value: str) -> HashGuess:
    text = value.strip()
    if _JWT.match(text):
        return HashGuess(
            label="JWT",
            next_step="That's a session token, not a password hash. Read the payload (it's base64), then decide whether to forge/resign — don't throw it at hashcat first.",
            confidence="high",
        )
    if _BCRYPT.match(text):
        return HashGuess(
            label="bcrypt",
            next_step="hashcat -m 3200 or john --format=bcrypt. Use a real wordlist (rockyou). This will be slow; that's normal.",
            confidence="high",
        )
    if _MD5CRYPT.match(text):
        return HashGuess(
            label="md5crypt ($1$)",
            next_step="hashcat -m 500 or john --format=md5crypt, then a wordlist.",
            confidence="high",
        )
    if _SHA512CRYPT.match(text):
        return HashGuess(
            label="sha512crypt ($6$)",
            next_step="hashcat -m 1800 or john --format=sha512crypt.",
            confidence="high",
        )
    if _HEX.match(text) and len(text) == 32:
        return HashGuess(
            label="md5 or NTLM (32-hex)",
            next_step=(
                "Can't tell md5 from NTLM by shape alone — both are 32 hex chars. "
                "If it came from a Windows SAM/NT/DCSync dump, try hashcat -m 1000 (NTLM) first. "
                "Otherwise hashcat -m 0 or john --format=raw-md5. Try rockyou before you invent a mask."
            ),
            confidence="medium",
        )
    if _HEX.match(text) and len(text) == 40:
        return HashGuess(
            label="sha1 (hex)",
            next_step="hashcat -m 100 or john --format=raw-sha1.",
            confidence="medium",
        )
    if _HEX.match(text) and len(text) == 64:
        return HashGuess(
            label="sha256 (hex)",
            next_step="hashcat -m 1400 or john --format=raw-sha256.",
            confidence="medium",
        )
    return HashGuess(
        label="unknown",
        next_step="Not a shape I recognize. Paste it into `trinity loot add --kind hash` so it stays on the box, then identify it with a local tool (hashid/haiti) — Trinity will not send it anywhere.",
        confidence="low",
    )
