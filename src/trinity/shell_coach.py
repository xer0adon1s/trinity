"""Shell Coach subsystem: a live, per-tool-session extension of
Shoulder Mode's pty capture, narrating and nudging through a
recognized interactive tool session. See
docs/COACH_SUBSYSTEM_DESIGN.md for the full design rationale before
touching this file.

NAMING NOTE: this is deliberately `shell_coach.py`, not `coach.py` --
`coach.py` already exists as Instructor Mode's suggestion-ranking
layer (a totally different "coach" concept: ranking `next`'s
persisted suggestions into a single recommendation). Don't rename
either module to make them match; they're unrelated systems that
happen to share a word in casual conversation, not in the codebase.

Architecture recap (see the design doc for the "why"):
  - ONE shared engine (this module) that any tool PROFILE plugs into
    as data — never a bespoke module per tool.
  - Reuses `hints.py`'s existing nudge -> stronger nudge -> answer
    escalation SHAPE (not its DB-backed suggestion_id state — a coach
    session is a live, in-memory, per-pty-session object, not a
    per-suggestion row).
  - Line-counted stall detection, not wall-clock timers: an operator
    who is reading output slowly produces no new lines either, so
    "N lines have passed with no recognized progress" is the same
    signal as "N seconds of silence" without needing a background
    timer thread, and it stays fully deterministic and unit-testable.

HARD RULE, non-negotiable (see design doc's "Hard rule" section):
this module only ever OBSERVES already-captured text and RETURNS
narration strings for the caller to print. It must never write bytes
back into the pty. If you are tempted to add a `send_input()` method
here — don't. That is the rail.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class CoachState:
    """One recognized step inside a tool's session. `recognize` marks
    "the operator/tool just did the thing this state represents";
    `expected_next` are patterns for on-track next moves out of this
    state (matching one just means "still on track", not a state
    transition — the state machine here is intentionally shallow,
    checklist-shaped rather than a strict graph, because real
    operator workflows branch and reorder more than a rigid graph
    would tolerate)."""

    name: str
    recognize: re.Pattern
    expected_next: list[re.Pattern] = field(default_factory=list)
    stall_nudge: str = ""
    stall_stronger_nudge: str = ""
    stall_answer: str = ""


@dataclass
class CoachProfile:
    """A pluggable tool definition. `prompt_pattern` recognizes "the
    operator just entered this tool's session"; `exit_pattern`
    recognizes the session ending. `states` are checked in order —
    first match wins — so put more specific patterns first."""

    tool_id: str
    display_name: str
    prompt_pattern: re.Pattern
    exit_pattern: re.Pattern
    states: list[CoachState]
    announce: str = ""


# Stall threshold: how many consecutive lines can pass with zero
# recognized progress (no new state entered, no expected_next pattern
# matched) before the coach speaks up. Deliberately conservative and
# small (an operator legitimately reading a long `id` or `sudo -l`
# output shouldn't get interrupted) — same "pick something
# conservative and document it" instruction the design doc leaves for
# the builder. Tune later against real usage, not guessed forever.
STALL_LINE_THRESHOLD = 8


@dataclass
class CoachSession:
    """Live, in-memory, one-per-watched-pty-session state. Call
    `feed_line()` once per new line of captured pty output; it
    returns a narration string to print, or None if there's nothing
    to say yet. This is the ONLY entry point callers need — profile
    matching, state tracking, and stall-ladder escalation all happen
    inside `feed_line()`.
    """

    profiles: list[CoachProfile]
    active_profile: CoachProfile | None = None
    active_state: CoachState | None = None
    stall_counter: int = 0
    stall_level: int = 0  # 0 = no stall yet, 1/2/3 = ladder rung, mirrors hints.py's shape

    def feed_line(self, line: str) -> str | None:
        if self.active_profile is None:
            return self._try_enter_profile(line)
        return self._advance_active_profile(line)

    def _try_enter_profile(self, line: str) -> str | None:
        for profile in self.profiles:
            if profile.prompt_pattern.search(line):
                self.active_profile = profile
                self.active_state = None
                self.stall_counter = 0
                self.stall_level = 0
                # The same line that triggered entry may ALSO match one
                # of this profile's states (e.g. raw-shell's own
                # prompt pattern doubles as its first state's
                # recognize pattern) -- check immediately so a stalled
                # operator has an active_state to nudge against right
                # away, instead of needing a second matching line.
                for state in profile.states:
                    if state.recognize.search(line):
                        self.active_state = state
                        break
                return profile.announce or f"Looks like you're in {profile.display_name} now."
        return None

    def _advance_active_profile(self, line: str) -> str | None:
        profile = self.active_profile
        assert profile is not None

        if profile.exit_pattern.search(line):
            self.active_profile = None
            self.active_state = None
            self.stall_counter = 0
            self.stall_level = 0
            return None

        # Check for entry into a NEW state first (specific-before-stall,
        # same "specific-before-general" ordering discipline shoulder.py
        # already uses for its own milestone patterns).
        for state in profile.states:
            if state.recognize.search(line):
                if state is not self.active_state:
                    self.active_state = state
                    self.stall_counter = 0
                    self.stall_level = 0
                return None

        # No new state entered. If we're inside a known state, check
        # whether this line is still "on track" (matches one of the
        # current state's expected next moves) before counting it as
        # a stall — an on-track line resets the counter without
        # forcing a state transition.
        if self.active_state is not None:
            for pattern in self.active_state.expected_next:
                if pattern.search(line):
                    self.stall_counter = 0
                    return None

        self.stall_counter += 1
        if self.stall_counter < STALL_LINE_THRESHOLD:
            return None

        self.stall_counter = 0
        self.stall_level = min(self.stall_level + 1, 3)
        state = self.active_state
        if state is None:
            return None
        if self.stall_level == 1:
            return state.stall_nudge or None
        if self.stall_level == 2:
            return state.stall_stronger_nudge or None
        return state.stall_answer or None


# --- First-wave profile: raw landed shell ---
#
# Deliberately the cheapest possible proof of the engine (per the
# design doc's build order): no external tool's own prompt format to
# parse — this profile's "session started" signal REUSES
# shoulder.py's existing shell-landed detection patterns rather than
# inventing a new one, and its states are a real, standard post-
# foothold checklist rather than a graph with branches.

_RAW_SHELL_PROMPT = re.compile(
    r"uid=\d+\([^)]+\).*gid=\d+|^\$ $|www-data@|Microsoft Windows \[Version|PS [A-Z]:\\\S*>",
    re.MULTILINE,
)
_RAW_SHELL_EXIT = re.compile(r"^logout$|^exit$|Connection closed by|Connection to .* closed")

_RAW_SHELL_STATES = [
    CoachState(
        name="landed",
        recognize=_RAW_SHELL_PROMPT,
        expected_next=[
            re.compile(r"^\s*(id|whoami)\b"),
            re.compile(r"python3? -c .*pty\.spawn|script -qc|/bin/sh -i"),
        ],
        stall_nudge=(
            "You've got a shell — before going further, it's worth stabilizing "
            "it and confirming who you are. What's usually the first thing "
            "worth checking about a fresh shell?"
        ),
        stall_stronger_nudge=(
            "A raw reverse/bind shell is usually fragile (no job control, no "
            "tab-complete, dies on Ctrl-C). Stabilizing it first with a proper "
            "TTY makes everything after this easier — and you still don't know "
            "which user you landed as."
        ),
        stall_answer=(
            "Run `id` (or `whoami`) to confirm your user, then stabilize the "
            "shell, e.g.: `python3 -c 'import pty; pty.spawn(\"/bin/bash\")'`"
        ),
    ),
    CoachState(
        name="identified",
        recognize=re.compile(r"^uid=\d+\([^)]+\)\(gid="),
        expected_next=[
            re.compile(r"sudo -l"),
            re.compile(r"find / .*-perm|find / .*4000"),
            re.compile(r"crontab|/etc/cron"),
        ],
        stall_nudge=(
            "You know who you are now — what would normally be worth checking "
            "next to see what THIS user is allowed to do?"
        ),
        stall_stronger_nudge=(
            "Two of the most common quick privesc checks: what can this user "
            "run as another user/root without a password, and are there any "
            "SUID binaries lying around?"
        ),
        stall_answer=(
            "Try `sudo -l` (what you can run as another user), and "
            "`find / -perm -4000 -type f 2>/dev/null` (SUID binaries)."
        ),
    ),
]

RAW_SHELL_PROFILE = CoachProfile(
    tool_id="raw_shell",
    display_name="a landed shell",
    prompt_pattern=_RAW_SHELL_PROMPT,
    exit_pattern=_RAW_SHELL_EXIT,
    states=_RAW_SHELL_STATES,
    announce=(
        "Looks like you've landed a shell. I'll narrate here if you seem "
        "stuck — I'm only watching, I won't type anything for you."
    ),
)


# --- Second profile: msfconsole ---
#
# First real external-tool prompt (raw-shell reused Shoulder Mode's
# already-known landing patterns). Prompt text is taken from
# metasploit-framework's driver.rb `update_prompt`:
#   DefaultPrompt = "%undmsf%clr", DefaultPromptChar = "%clr>"
#   and with a module selected:
#     "#{Prompt} #{type}(%bld%red#{promptname}%clr)"
# After Rex color substitution the visible defaults are `msf6 >`
# (or `msf5 >` / `msf >` on older frameworks) and
# `msf6 exploit(windows/smb/ms17_010_eternalblue) >` (also
# auxiliary/payload/post/encoder/nop/evasion). Optional ANSI CSI
# sequences are tolerated because a live pty chunk still has the
# underline/bold-red codes; we could not launch msfconsole here to
# paste a real capture (`which msfconsole` missed).
#
# Commands are matched as "prompt + typed command" because that is
# how a pty records a line (`msf6 > search eternalblue`), and
# because `help` output lists the words `search`/`use`/`exit` as
# bare columns that would false-trigger a start-of-line match.
#
# State order is specific-before-general (see CoachProfile): fired
# and options_set must beat module_selected, because after `use`
# almost every line reprints the module-context prompt. The module
# prompt itself is NOT a state recognize — it reprints after every
# command and would clobber later states under first-match-wins
# (logged in docs/COACH_OPEN_QUESTIONS.md). `use` is the one-shot
# signal that a module was actually selected.

_MSF_ANSI = r"(?:\x1b\[[0-9;]*m)*"
_MSF_MODULE_TYPE = r"(?:exploit|auxiliary|payload|post|encoder|nop|evasion)"
_MSF_MODULE_CTX = (
    rf"{_MSF_MODULE_TYPE}{_MSF_ANSI}\({_MSF_ANSI}[^)\r\n]+{_MSF_ANSI}\)"
)
# `msf` + optional version digits so `msf`, `msf5`, `msf6`, and a
# future `msf7` all match; `msfconsole >` does not, because the
# leftover "console" sits where a space-or-`>` must be.
_MSF_PROMPT = (
    rf"{_MSF_ANSI}msf\d*{_MSF_ANSI}"
    rf"(?:\s+{_MSF_ANSI}{_MSF_MODULE_CTX}{_MSF_ANSI})?"
    rf"\s*{_MSF_ANSI}>"
)


def _msf_at_prompt(command: str) -> re.Pattern:
    """A command typed at the msfconsole prompt (case-insensitive —
    the console treats `set RHOSTS` and `set rhosts` the same)."""
    return re.compile(rf"{_MSF_PROMPT}\s*{command}", re.IGNORECASE)


_MSF_PROMPT_LINE = re.compile(_MSF_PROMPT)
# `exit -y` skips the "you have active jobs" confirm; `quit` is the
# documented alias. The user@host OS prompt is the "msfconsole just
# closed and the surrounding shell came back" signal — see open
# questions for fancy Kali two-line prompts this will miss.
_MSF_EXIT = re.compile(
    rf"{_MSF_PROMPT}\s*(?:exit|quit)\b"
    r"|^\S+@\S+[: ].*[$#]\s*$",
    re.IGNORECASE | re.MULTILINE,
)

_MSFCONSOLE_STATES = [
    CoachState(
        name="fired",
        recognize=_msf_at_prompt(r"(?:run|exploit)\b"),
        expected_next=[
            _msf_at_prompt(r"sessions\b"),
        ],
        stall_nudge=(
            "It ran — before I tell you what to type, how would you "
            "usually tell whether that actually got you a foothold?"
        ),
        stall_stronger_nudge=(
            "A successful run opens a session, and you haven't listed "
            "or entered one yet."
        ),
        stall_answer=(
            "Run `sessions -l` to list active sessions, then "
            "`sessions -i <id>` to interact with one."
        ),
    ),
    CoachState(
        name="options_set",
        # RHOSTS (and the older singular RHOST) is the "told it what
        # to attack" signal; LHOST/payload stay expected_next on
        # module_selected so setting a callback address alone does
        # not pretend the module is ready to fire.
        recognize=_msf_at_prompt(r"setg?\s+rhosts?\b"),
        expected_next=[
            _msf_at_prompt(r"(?:run|exploit|check)\b"),
        ],
        stall_nudge=(
            "The target is set — what's the usual next move once a "
            "module knows where to point?"
        ),
        stall_stronger_nudge=(
            "Options are filled in but the module hasn't been launched yet."
        ),
        stall_answer=(
            "Run `run` or `exploit` (or `check` first if you want to "
            "test without firing)."
        ),
    ),
    CoachState(
        name="searching",
        recognize=_msf_at_prompt(r"search\b"),
        expected_next=[
            _msf_at_prompt(r"use\s+\S+"),
        ],
        stall_nudge=(
            "You've got results back — what would you normally do "
            "with a module that looks relevant?"
        ),
        stall_stronger_nudge=(
            "You've searched but haven't picked a module yet — "
            "selecting one is what actually changes the console's context."
        ),
        stall_answer=(
            "Pick one with `use <module/path>` (or `use <number>` "
            "from the search-results index)."
        ),
    ),
    CoachState(
        name="module_selected",
        recognize=_msf_at_prompt(r"use\s+\S+"),
        expected_next=[
            _msf_at_prompt(r"(?:show\s+)?options\b"),
            _msf_at_prompt(r"setg?\s+(?:rhosts?|lhost|lport|payload)\b"),
        ],
        stall_nudge=(
            "You've picked something — what does it still need to "
            "know before it can do anything useful?"
        ),
        stall_stronger_nudge=(
            "You've picked a module but haven't told it what to attack yet."
        ),
        stall_answer=(
            "Set the target with `set RHOSTS <target>` (and often "
            "`set LHOST <your-ip>` for a reverse payload). "
            "`show options` lists what's required."
        ),
    ),
]

MSFCONSOLE_PROFILE = CoachProfile(
    tool_id="msfconsole",
    display_name="msfconsole",
    prompt_pattern=_MSF_PROMPT_LINE,
    exit_pattern=_MSF_EXIT,
    states=_MSFCONSOLE_STATES,
    announce=(
        "Looks like you're in msfconsole. I'll narrate here if you seem "
        "stuck — I'm only watching, I won't type anything for you."
    ),
)


DEFAULT_PROFILES: list[CoachProfile] = [RAW_SHELL_PROFILE, MSFCONSOLE_PROFILE]


def new_session(profiles: list[CoachProfile] | None = None) -> CoachSession:
    """Convenience constructor — defaults to the shipped profile set."""
    return CoachSession(profiles=list(profiles) if profiles is not None else list(DEFAULT_PROFILES))
