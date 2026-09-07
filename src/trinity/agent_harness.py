"""Agent Harness: Trinity's mechanism for filling a genuine local-cache
gap by calling out to the OPERATOR'S OWN agent CLI -- never a hosted
API key Trinity holds itself, never an in-app chat pane. See
docs/AGENT_HARNESS.md for the full design and the precise line this
does NOT cross.

Detection priority (docs/AGENT_HARNESS.md):
1. Omarchy's default agent, if running on Omarchy.
2. Any detected agent CLI on PATH otherwise.
3. None found -> caller falls back to the existing manual copy-paste
   escalation flow (build_escalation_prompt/build_error_escalation_prompt).

Every call is a single, bounded, non-interactive invocation for one
specific question -- never a persistent session, never a chat.
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_OMARCHY_AGENT_DEFAULTS_FILE = Path.home() / ".config" / "omarchy" / "defaults" / "agent"

# Known agent CLI binaries, checked in this order when not on Omarchy
# (or when Omarchy's own default doesn't resolve to anything usable).
# Same shape as tools.py's registry: small, hand-maintained, PR-able.
# `invoke_args` builds the one-shot/non-interactive argv for a given
# prompt -- exact flags differ per tool and may need adjustment as
# these CLIs evolve; this is intentionally a thin, easily-fixed layer.
@dataclass
class AgentInfo:
    name: str
    check_binary: str
    invoke_args: Callable[[str], list[str]]


def _hermes_args(prompt: str) -> list[str]:
    return ["hermes", "--prompt", prompt]


def _claude_args(prompt: str) -> list[str]:
    return ["claude", "-p", prompt]


def _codex_args(prompt: str) -> list[str]:
    return ["codex", "exec", prompt]


def _gemini_args(prompt: str) -> list[str]:
    return ["gemini", "-p", prompt]


def _cursor_agent_args(prompt: str) -> list[str]:
    return ["cursor-agent", "-p", prompt]


# Order matters: this is also the PATH-scan fallback order when not on
# Omarchy (or Omarchy's own configured default doesn't resolve).
_KNOWN_AGENTS: list[AgentInfo] = [
    AgentInfo("hermes", "hermes", _hermes_args),
    AgentInfo("claude", "claude", _claude_args),
    AgentInfo("codex", "codex", _codex_args),
    AgentInfo("gemini", "gemini", _gemini_args),
    AgentInfo("cursor-agent", "cursor-agent", _cursor_agent_args),
]

_AGENTS_BY_NAME = {a.name: a for a in _KNOWN_AGENTS}


def is_omarchy() -> bool:
    """Best-effort Omarchy detection -- same defensive pattern as
    platform_registry.py's get_omarchy_theme(): try, fall back
    cleanly, never crash on a non-Omarchy system."""
    try:
        return _OMARCHY_AGENT_DEFAULTS_FILE.exists()
    except OSError:
        return False


def _omarchy_default_agent_name() -> str | None:
    """Reads Omarchy's configured default agent. Note: as of writing,
    Omarchy's own defaults/agent file may still say 'claude' even on
    installs where the actual launched Quake-console agent is Hermes
    (see the omarchy-hyprland skill notes) -- this reads the file
    honestly and lets is_agent_available() correct for a stale/
    unresolvable value by falling through to the PATH scan."""
    try:
        text = _OMARCHY_AGENT_DEFAULTS_FILE.read_text().strip().lower()
        return text or None
    except OSError:
        return None


def is_agent_available(name: str) -> bool:
    info = _AGENTS_BY_NAME.get(name)
    if info is None:
        return False
    return shutil.which(info.check_binary) is not None


def detect_agent() -> AgentInfo | None:
    """The actual priority order from docs/AGENT_HARNESS.md: Omarchy's
    default agent first (if it resolves to something actually on
    PATH), then any known agent CLI found on PATH, in registry order.
    Returns None if nothing usable was found -- callers must fall back
    to the manual copy-paste flow, never assume an agent exists."""
    if is_omarchy():
        default_name = _omarchy_default_agent_name()
        # Prefer Hermes specifically if it's on PATH and Omarchy is in
        # play -- Hermes is the recommended/expected agent harness for
        # this project's own reference environment even when the raw
        # defaults file still says something else (a known drift; see
        # _omarchy_default_agent_name's note).
        if is_agent_available("hermes"):
            return _AGENTS_BY_NAME["hermes"]
        if default_name and is_agent_available(default_name):
            return _AGENTS_BY_NAME[default_name]

    for agent in _KNOWN_AGENTS:
        if is_agent_available(agent.name):
            return agent
    return None


def invoke_agent(agent: AgentInfo, prompt: str, timeout: float = 120.0) -> str | None:
    """Runs a single, bounded, non-interactive call to the given agent
    CLI with the given prompt. Returns the captured stdout, or None on
    any failure (missing binary, timeout, non-zero exit, unexpected
    error) -- a harness call failing must never crash Trinity or block
    the existing manual-escalation fallback. Never invoked in a loop,
    never given a persistent session -- one question, one answer."""
    try:
        result = subprocess.run(
            agent.invoke_args(prompt),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def ask_agent(prompt: str, timeout: float = 120.0) -> tuple[str | None, str | None]:
    """The main entry point: detects an agent, asks it the given
    prompt, returns (answer, agent_name_used) -- both None if no
    agent was found or the call failed. Callers (explain_cmd,
    error_cmd, gtfobins proactive nudges, Methods Index live drafting)
    are responsible for routing a real answer through
    intake.submit_candidate() for review -- this function never writes
    to any KB/cache table itself."""
    agent = detect_agent()
    if agent is None:
        return None, None
    answer = invoke_agent(agent, prompt, timeout=timeout)
    if answer is None:
        return None, None
    return answer, agent.name
