"""Show Me Mode (docs/SHOW_ME_MODE.md): Trinity's own agent attempts
ONE milestone step live, in its OWN execution session -- never the
student's terminal -- then hands back the exact recipe for the
student to run themselves. This is Assimilator's LIVE trigger (see
docs/ASSIMILATOR_PROJECT.md §2 and src/trinity/assimilator.py) --
same diagnose/hypothesize/verify/land loop, just triggered on-demand
against a real target instead of Doc's offline fixture sweep.

Architecture note (the "her own window" correction, and why this is a
NEW module rather than reusing shoulder.py): shoulder.py is read-only
by design ("never writes to or filters the pty") and cannot host this.
This module also does NOT hand the agent a raw interactive shell --
per both design reviews' recommendation, the agent PROPOSES one
command at a time (via the existing bounded, non-streaming
agent_harness.invoke_agent -- no new agent integration), and Trinity's
own runner EXECUTES it after checking the destructive-command
denylist and the target pin. The agent never gets live shell access
itself. This is deliberately a tighter, more auditable loop than a
true pty session -- every command that ran is in the transcript before
the agent sees the next one.

Always-available by design (docs/OPEN_DECISIONS.md's "Auto-run scans
or exploits" entry, per Alexander's explicit call): no Rabbit Hole
Detection stuck-gate, no hardcoded target allowlist -- an
authorization attestation instead.
"""
from __future__ import annotations

import json
import re
import shlex
import sqlite3
import subprocess
from datetime import UTC, datetime

from pydantic import BaseModel

from trinity.agent_harness import detect_agent, invoke_agent
from trinity.assimilator import check_already_known, finish_run, start_run
from trinity.boxes import get_box
from trinity.milestones import record_shell
from trinity.timeline import log_event

VALID_MILESTONES = {"foothold", "privesc_to_user", "privesc_to_root"}

# Hard caps (docs/SHOW_ME_MODE.md §6). Not configurable upward from a
# file in v1 -- see the same doc's §9 open question #3 on cost/rate
# limiting; these are deliberately conservative starting points.
MAX_COMMANDS = 12
MAX_AGENT_TURNS = 12
COMMAND_TIMEOUT_S = 60

# Destructive-command denylist, enforced by the RUNNER before
# execution -- not a prompt asking the agent to be careful (both
# reviews flagged "the AI's role is bounded" as unenforceable if it's
# only a prompt instruction). Matched against the full command string;
# deliberately broad/conservative for v1, easy to extend.
_DENYLIST_PATTERNS = [
    r"\brm\s+-rf\b", r"\bmkfs\b", r"\bdd\s+if=", r">\s*/dev/sd",
    r"\bshutdown\b", r"\breboot\b", r"\bpoweroff\b",
    r"\biptables\b", r"\bufw\b",
    r"\bservice\s+\S+\s+(stop|restart)\b", r"\bsystemctl\s+(stop|restart|disable)\b",
    r"\bpasswd\b", r"\buserdel\b", r"\bkillall\b",
]
_DENYLIST_RE = re.compile("|".join(_DENYLIST_PATTERNS), re.IGNORECASE)


class DisclosureText(BaseModel):
    banner: str


def build_disclosure(agent_name: str | None, milestone: str) -> DisclosureText:
    """The per-invocation, non-skippable disclosure (docs/SHOW_ME_MODE.md
    §7). Always shown, every time -- no --yes flag, no env-var bypass."""
    agent_label = agent_name or "your agent CLI"
    banner = (
        f"Show Me Mode: {agent_label} will attempt ONE step ({milestone}) live, "
        "in ITS OWN session, against this target -- not your terminal. "
        f"You'll watch it work (up to {MAX_COMMANDS} commands, "
        f"{MAX_AGENT_TURNS} turns). If it succeeds, you'll get the exact "
        "recipe to run yourself; that's what counts as your own progress, "
        "not this session."
    )
    return DisclosureText(banner=banner)


def has_attestation(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT 1 FROM show_me_attestation WHERE id = 1").fetchone()
    return row is not None


def record_attestation(conn: sqlite3.Connection) -> None:
    """One-time authorization acknowledgment (docs/SHOW_ME_MODE.md §4)
    -- same legal shape as any pentest tool's terms-of-use checkbox.
    Deliberately NOT a per-box allowlist (explicitly rejected, see
    docs/OPEN_DECISIONS.md's 'Auto-run scans or exploits' entry)."""
    conn.execute(
        "INSERT INTO show_me_attestation (id, accepted_at) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET accepted_at = excluded.accepted_at",
        (datetime.now(UTC).isoformat(),),
    )
    conn.commit()


ATTESTATION_TEXT = (
    "Show Me Mode lets your agent CLI attempt live steps against targets "
    "you use Trinity against. This is a real capability with real risk -- "
    "only use it against systems you are authorized to test (retired "
    "practice boxes, your own lab, or engagements you're contracted for). "
    "You are responsible for your own authorization. Trinity does not "
    "verify targets."
)


def is_command_allowed(command: str, target: str) -> tuple[bool, str | None]:
    """The runner's own decision, not the agent's. Returns (allowed,
    reason_if_not). Checked before EVERY command executes."""
    if _DENYLIST_RE.search(command):
        return False, "matches the destructive-command denylist"
    # Target pin: if the command references a host-shaped token that
    # isn't the box's own target (or localhost, for local pivots),
    # refuse it. Deliberately conservative regex, not a full parser --
    # false refusals (over-blocking) are the safe failure direction
    # here, false allows are not.
    host_tokens = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", command)
    for token in host_tokens:
        if token not in (target, "127.0.0.1", "0.0.0.0"):
            return False, f"references a host ({token}) that isn't the box's target"
    return True, None


class ShowMeResult(BaseModel):
    outcome: str            # 'succeeded' | 'aborted' | 'failed' | 'already_known'
    milestone: str
    agent_used: str | None
    commands_run: list[str]
    recipe_for_student: str | None
    already_known_title: str | None = None
    stop_reason: str | None = None


def _milestone_reached(milestone: str, shell_level: str | None) -> bool:
    if milestone == "foothold":
        return shell_level in ("user", "root")
    if milestone == "privesc_to_user":
        return shell_level in ("user", "root")
    if milestone == "privesc_to_root":
        return shell_level == "root"
    return False


def _detect_shell_evidence(output: str) -> str | None:
    """Reuses the same conservative pattern discipline as
    shoulder.py's scan_for_milestones -- deliberately not importing
    that function directly (it's part of a read-only module with its
    own invariants; duplicating the small regex here keeps this
    module's dependency surface honest, see the module docstring)."""
    if re.search(r"uid=0\(root\)|root@\S+:.*#\s*$", output, re.MULTILINE):
        return "root"
    if re.search(r"uid=\d+\([^)]+\).*gid=\d+|www-data@|\$\s*$", output, re.MULTILINE):
        return "user"
    return None


def run_show_me(
    conn: sqlite3.Connection,
    box_id: int,
    milestone: str,
) -> ShowMeResult:
    """The core live-execution loop. Agent proposes one command via a
    bounded invoke_agent call; the runner checks it against the
    denylist/target-pin, executes it (in Trinity's own subprocess, NOT
    the student's shell), feeds the output back, and repeats until the
    milestone is reached or a hard cap fires. See module docstring for
    why this is propose-then-execute rather than a raw agent shell."""
    if milestone not in VALID_MILESTONES:
        raise ValueError(f"milestone must be one of {VALID_MILESTONES}, got {milestone!r}")

    box = get_box(conn, box_id)
    if box is None:
        raise ValueError(f"No box with id {box_id}")
    if not box.target:
        raise ValueError("Box has no target set -- Show Me Mode needs a real target to run against.")

    agent = detect_agent()
    agent_name = agent.name if agent else None

    run_id = start_run(
        conn, "live", "capability_gap",  # provisional cause; refined at finish
        box_id=box_id, hypothesis=f"live attempt at milestone={milestone}",
        verification_method="live_target",
    )

    commands_run: list[str] = []
    transcript = ""
    result = ShowMeResult(
        outcome="failed", milestone=milestone, agent_used=agent_name,
        commands_run=commands_run, recipe_for_student=None,
    )

    if agent is None:
        finish_run(conn, run_id, "rejected_hypothesis")
        result.outcome = "failed"
        result.stop_reason = "no agent CLI detected on PATH"
        conn.execute(
            "INSERT INTO show_me_runs (box_id, milestone, agent_used, outcome, commands_run) "
            "VALUES (?, ?, ?, ?, ?)",
            (box_id, milestone, None, "failed", json.dumps([])),
        )
        conn.commit()
        return result

    for _turn in range(MAX_AGENT_TURNS):
        if len(commands_run) >= MAX_COMMANDS:
            result.stop_reason = "max command cap reached"
            break

        prompt = (
            f"You are attempting to reach the '{milestone}' milestone against "
            f"a CTF/pentest practice target at {box.target}. This is an "
            "authorized practice box. Respond with ONLY a single shell "
            "command (no explanation, no markdown) that is the single best "
            "next step, given this transcript so far:\n\n"
            f"{transcript or '(nothing run yet)'}\n\n"
            "If you believe the milestone is already reached based on the "
            "transcript, respond with exactly: DONE"
        )
        proposal = invoke_agent(agent, prompt, timeout=COMMAND_TIMEOUT_S)
        if proposal is None:
            result.stop_reason = "agent call failed or timed out"
            break

        proposal = proposal.strip()
        if proposal.upper() == "DONE":
            break

        # Agent may wrap the command in markdown/backticks; take the
        # first non-empty line as the literal command.
        command = next((line.strip().strip("`") for line in proposal.splitlines() if line.strip()), "")
        if not command:
            continue

        allowed, reason = is_command_allowed(command, box.target)
        if not allowed:
            transcript += f"$ {command}\n[REFUSED by Trinity: {reason}]\n"
            log_event(conn, box_id, "show_me_refused", f"refused command: {command}",
                      phase="privesc" if "privesc" in milestone else "foothold", detail=reason)
            continue

        try:
            proc = subprocess.run(
                shlex.split(command), capture_output=True, text=True,
                timeout=COMMAND_TIMEOUT_S, check=False,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            output = f"[execution error: {exc}]"

        commands_run.append(command)
        transcript += f"$ {command}\n{output}\n"

        shell_evidence = _detect_shell_evidence(output)
        if shell_evidence:
            record_shell(conn, box_id, shell_evidence)
            refreshed = get_box(conn, box_id)
            if refreshed and _milestone_reached(milestone, refreshed.shell_level):
                result.outcome = "succeeded"
                result.recipe_for_student = "\n".join(commands_run)
                break

    result.commands_run = commands_run

    if result.outcome != "succeeded":
        finish_run(conn, run_id, "rejected_hypothesis" if not result.stop_reason
                   else "escalated_capability_gap")
        conn.execute(
            "INSERT INTO show_me_runs (box_id, milestone, agent_used, outcome, commands_run) "
            "VALUES (?, ?, ?, ?, ?)",
            (box_id, milestone, agent_name, result.outcome, json.dumps(commands_run)),
        )
        conn.commit()
        return result

    # Success: check whether this was actually already in the KB
    # (Alexander's explicit ask -- "tell the user it may have missed a
    # solution that was already programmed in").
    already_known = check_already_known(conn, service=None, product=None, version=None, detail=transcript)
    if already_known:
        result.outcome = "already_known"
        result.already_known_title = already_known.title
        finish_run(conn, run_id, "already_known", already_known_hit=True, self_lifted=True)
    else:
        finish_run(conn, run_id, "verified_fix", self_lifted=True)

    conn.execute(
        "INSERT INTO show_me_runs (box_id, milestone, agent_used, outcome, commands_run, "
        "recipe_for_student, assimilator_run_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (box_id, milestone, agent_name, result.outcome, json.dumps(commands_run),
         result.recipe_for_student, run_id),
    )
    conn.commit()

    log_event(
        conn, box_id, "show_me_result",
        f"Show Me Mode reached {milestone}" + (" (already in KB)" if already_known else ""),
        phase="privesc" if "privesc" in milestone else "foothold",
        detail=result.recipe_for_student,
    )
    return result


def has_any_show_me_runs(conn: sqlite3.Connection, box_id: int) -> bool:
    """Used by report rendering to decide whether the mandatory
    AI-assistance disclosure block must appear (docs/SHOW_ME_MODE.md
    §7 -- never suppressible)."""
    row = conn.execute("SELECT 1 FROM show_me_runs WHERE box_id = ? LIMIT 1", (box_id,)).fetchone()
    return row is not None


def get_show_me_runs(conn: sqlite3.Connection, box_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM show_me_runs WHERE box_id = ? ORDER BY id", (box_id,)
    ).fetchall()
