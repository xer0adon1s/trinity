"""PROTOTYPE — critical-match desktop ping (Trinity_suggestions.md 2.11).

Best-effort `notify-send`. Missing binary or a failed spawn is silent.
Never runs an exploit. Deduped by the caller.
"""
from __future__ import annotations

import shutil
import subprocess


def notify_critical(title: str, body: str) -> bool:
    binary = shutil.which("notify-send")
    if not binary:
        return False
    try:
        subprocess.run(
            [binary, "--expire-time=8000", title, body],
            check=False,
            capture_output=True,
            timeout=3,
        )
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False
