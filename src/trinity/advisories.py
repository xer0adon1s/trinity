"""Advisory arbitration for `trinity next` (docs/FEATURES_BACKLOG.md,
"structural fix"): the real problem behind next's output stacking up
to 8+ lines was never "too much text" -- it was that several unrelated
features (unlocks, rabbit-hole, frustration, AutoRecon graduation, the
difficulty note) each independently decided they were allowed to print
directly to the console with zero awareness of each other. A flat
character cap would only truncate the pileup after the fact and pick
an arbitrary winner (whatever happened to print last); it wouldn't fix
the actual coordination problem, and it wouldn't compose into readable
prose.

This module is the fix: a small, ordered registry of "advisory
providers." Each provider is a plain function that inspects the
current box/recommendation and returns an Advisory (or None if it has
nothing to say right now). `next_cmd` asks the registry for every
provider's opinion, in priority order, and takes ONLY the single
highest-priority one that actually has something to say. Everything
else is silently deferred to a future call -- never lost, never shown
alongside the winner. This also means an urgent thing (you've been
stuck for 20 minutes) can never get visually buried under a routine
thing (there's an optional curiosity card waiting).

Zero AI: every provider here inspects deterministic local state
(timeline queries, hint counts, box fields) and returns pre-written
text. There's no ambiguity to resolve -- the hard part was always
arbitration, not interpretation -- so this stays fully local, instant,
and free, consistent with DESIGN.md's "local-first, agent-assisted,
never a chat pane" principle. The composed sentence still routes
through phrasebook.py's data-driven-phrase pattern so it reads as one
paragraph, not a mechanical prefix + bullet.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Callable

from pydantic import BaseModel

from trinity.boxes import Box


class Advisory(BaseModel):
    kind: str            # matches the provider's identity, for logging/tests
    priority: int         # LOWER number wins -- 0 is most urgent
    sentence: str          # one flowing clause/sentence, composable into prose
    alternative_command: str | None = None  # optional "untouched lead" to surface
    offers_methods_index: bool = False  # one-shot: see _MODIS_EVENT_TYPE below


AdvisoryProvider = Callable[[sqlite3.Connection, Box], "Advisory | None"]

# Event type used to gate the Methods Index escape-hatch offer so it
# fires once per stuck episode, not on every subsequent `next` call
# while still stuck -- same one-shot-via-timeline-event principle as
# graduation.py's autorecon_nudge/mark_nudged pair (docs/FEATURES_BACKLOG.md
# explicitly calls out reusing that pattern here). Kept distinct from
# rabbit_hole.py's own "nudge" event type so this doesn't double-log or
# interfere with recent_nudge_count()'s escalating-checkpoint-text math.
_METHODS_OFFER_EVENT_TYPE = "methods_index_offer"


def _methods_offer_already_shown(conn: sqlite3.Connection, box_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM timeline WHERE box_id = ? AND event_type = ? LIMIT 1",
        (box_id, _METHODS_OFFER_EVENT_TYPE),
    ).fetchone()
    return row is not None


def _mark_methods_offered(conn: sqlite3.Connection, box_id: int) -> None:
    from trinity.timeline import log_event

    log_event(conn, box_id, _METHODS_OFFER_EVENT_TYPE, "Methods Index escape-hatch offered")


def _difficulty_advisory(conn: sqlite3.Connection, box: Box) -> Advisory | None:
    # PROTOTYPE (difficulty-aware): quiet, only for Hard. Easy stays
    # silent so we don't imply they should already be done.
    if box.difficulty == "hard":
        return Advisory(
            kind="difficulty", priority=40,
            sentence="it's listed as Hard, so taking a long time here is normal, not a verdict",
        )
    return None


def _methods_index_offer(box: Box) -> str | None:
    """Escape-hatch offer text (docs/METHODS_INDEX.md, "How it surfaces
    to the operator"): pure invitation, never the content itself -- the
    operator has to run the command to actually see anything. Returns
    None when this box has no indexed entry, so the rabbit-hole
    advisory is left completely unchanged for boxes without one."""
    from trinity.methods import lookup

    index = lookup(box.name, platform=box.platform) or lookup(box.name)
    if index is None:
        return None
    return (
        "There are a few known shapes people have used to crack machines "
        f"like this — want to see them? Run `trinity methods --box \"{box.name}\"`"
    )


def _rabbit_hole_advisory(conn: sqlite3.Connection, box: Box) -> Advisory | None:
    from trinity.frustration import checkpoint_text
    from trinity.rabbit_hole import detect_rabbit_hole, log_nudge, recent_nudge_count

    signal = detect_rabbit_hole(conn, box.id)
    if signal is None:
        return None
    prior = recent_nudge_count(conn, box.id)
    extra = checkpoint_text(prior)
    # Logged at detection time regardless of whether this ends up
    # winning the single advisory slot -- matches the pre-existing
    # behavior (detection was always logged), and rabbit-hole is
    # priority 0 (most urgent) so in practice it always wins when
    # present anyway.
    log_nudge(conn, box.id, signal)
    sentence = signal.message
    if extra:
        sentence = f"{sentence} {extra}"

    # Methods Index escape-hatch offer (docs/METHODS_INDEX.md step 3):
    # additive to the stuck-signal sentence, ONLY when this box actually
    # has an indexed entry, and ONLY once per box -- mirroring
    # graduation.py's autorecon_nudge/mark_nudged one-shot-via-timeline-
    # event pattern (see _METHODS_OFFER_EVENT_TYPE above) rather than a
    # new mechanism. Marked at detection time here (not deferred to
    # pick_advisory like autorecon's nudge) because rabbit-hole is
    # always priority 0 and, per the comment above, always wins the
    # slot when present -- same reasoning already used for log_nudge().
    offers_methods_index = False
    if not _methods_offer_already_shown(conn, box.id):
        offer = _methods_index_offer(box)
        if offer:
            sentence = f"{sentence} {offer}"
            _mark_methods_offered(conn, box.id)
            offers_methods_index = True

    return Advisory(
        kind="rabbit_hole", priority=0,  # most urgent: an active stuck-signal
        sentence=sentence, alternative_command=signal.alternative_command,
        offers_methods_index=offers_methods_index,
    )


def _unlock_advisory(conn: sqlite3.Connection, box: Box) -> Advisory | None:
    from trinity.unlocks import peek_card

    card = peek_card(conn, box.id)
    if card is None:
        return None
    return Advisory(
        kind="unlock", priority=30,
        sentence=(
            "there's an optional curiosity card waiting on this "
            f"(`trinity unlock --box \"{box.name}\"`, skip by default)"
        ),
    )


def _autorecon_advisory(conn: sqlite3.Connection, box: Box) -> Advisory | None:
    from trinity.graduation import autorecon_nudge

    if box.mode == "professional":
        return None
    nudge = autorecon_nudge(conn, box.id)
    if nudge is None:
        return None
    return Advisory(kind="autorecon", priority=50, sentence=nudge)


# Registered in NO particular order here -- priority on each Advisory
# is what decides the winner, not registration order. Add a new
# provider by appending to this list; it automatically competes for
# the single advisory slot rather than needing its own cap negotiated
# against every other feature.
PROVIDERS: list[AdvisoryProvider] = [
    _rabbit_hole_advisory,
    _unlock_advisory,
    _difficulty_advisory,
    _autorecon_advisory,
]


def pick_advisory(conn: sqlite3.Connection, box: Box) -> Advisory | None:
    """Asks every registered provider for its opinion, returns only the
    single lowest-priority-number (most urgent) one with something to
    say. Everything else is silently deferred -- callers only ever see
    one winner, never a list.

    One-shot advisories (currently just AutoRecon's graduation nudge)
    are marked as shown ONLY here, on the actual winner -- never inside
    the provider itself at detection time. This matters: a nudge that
    was eligible but got outranked by something more urgent (e.g. a
    rabbit-hole stuck-signal) must stay eligible to win a LATER call,
    not get silently burned just because it was detected once."""
    candidates = [a for a in (provider(conn, box) for provider in PROVIDERS) if a is not None]
    if not candidates:
        return None
    winner = min(candidates, key=lambda a: a.priority)
    if winner.kind == "autorecon":
        from trinity.graduation import mark_nudged
        mark_nudged(conn, box.id)
    return winner
