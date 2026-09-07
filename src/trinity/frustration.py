"""PROTOTYPE — frustration checkpoints (FEATURES_BACKLOG.md).

Not a second detector. If rabbit-hole detection has already fired
once on this box, the *next* detection shows this copy instead of
repeating the same meta-skill lecture.
"""
from __future__ import annotations

ENCOURAGEMENT = (
    "Even people with security master's degrees get stuck for hours on "
    "'easy' boxes. This is normal, not a sign you're bad at this. "
    "Take a walk, then pick a lead you haven't touched — or keep "
    "pushing if you still believe this path. Both are legitimate."
)


def checkpoint_text(prior_nudge_count: int) -> str | None:
    if prior_nudge_count >= 1:
        return ENCOURAGEMENT
    return None
