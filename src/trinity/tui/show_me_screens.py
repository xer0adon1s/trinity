"""Modal screens for the watch dashboard's Tools and Advanced Options
menus (bound to the 't' and 'a' keys -- see dashboard.py's BINDINGS).
Kept in a separate module so dashboard.py doesn't grow an unrelated
pile of screen classes.

Split (Alexander's call): **Tools** is action-oriented -- things you
DO mid-session (Show Me Mode, loot, recap, lookups, report). **Advanced**
is config-oriented -- things you CHANGE about how Trinity behaves
going forward (mode, hacker name, sharing, engagement metadata). This
mirrors the CLI's own command shape and is meant to scale as the
program grows rather than becoming one flat, ever-longer menu.

Show Me Mode (docs/SHOW_ME_MODE.md, src/trinity/show_me.py) lives in
Tools as "[ (A)ssimilate Attack Vector ]" -- Alexander's explicit
naming, tying the UI label directly back to Assimilator
(src/trinity/assimilator.py) since Show Me Mode IS Assimilator's live
trigger, not a separately-branded feature. Before this, `trinity
show-me` was CLI-only and unreachable from inside `trinity watch` --
this closes that gap so testers never have to drop out of the
dashboard to use it.
"""
from __future__ import annotations

import sqlite3

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, ListItem, ListView, Static

from trinity.boxes import Box


class ToolsMenuScreen(ModalScreen[None]):
    """The 't' key's menu: action-oriented, mid-session tools."""

    DEFAULT_CSS = """
    ToolsMenuScreen {
        align: center middle;
    }
    #tools-menu {
        width: 64;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss_screen", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="tools-menu"):
            yield Label("[bold]Tools[/bold]")
            yield ListView(
                ListItem(Label("[ (A)ssimilate Attack Vector ] — Show Me Mode"), id="opt-show-me"),
                ListItem(Label("Add loot (credential/hash/token/flag)"), id="opt-loot-add"),
                ListItem(Label("List loot recorded so far"), id="opt-loot-list"),
                ListItem(Label("Recap this box"), id="opt-recap"),
                ListItem(Label("Look up a GTFOBins binary"), id="opt-gtfobins"),
                ListItem(Label("Classify a hash/token"), id="opt-hash"),
                ListItem(Label("Health check (doctor)"), id="opt-doctor"),
                id="tools-list",
            )
            yield Static("[dim]Esc to close[/dim]")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        self.dismiss(None)
        app = self.app
        box, conn = app.box, app.conn  # type: ignore[attr-defined]

        if item_id == "opt-show-me":
            app.push_screen(ShowMeAttestationScreen(box, conn))
        elif item_id == "opt-loot-add":
            app.push_screen(LootAddScreen(box, conn))
        elif item_id == "opt-loot-list":
            app.push_screen(LootListScreen(box, conn))
        elif item_id == "opt-recap":
            app.push_screen(RecapScreen(box, conn))
        elif item_id == "opt-gtfobins":
            app.push_screen(GtfobinsLookupScreen())
        elif item_id == "opt-hash":
            app.push_screen(HashLookupScreen())
        elif item_id == "opt-doctor":
            app.push_screen(DoctorScreen())


class _TextResultScreen(ModalScreen[None]):
    """Shared shape for the several Tools screens that are just
    "show some text, esc to close" -- recap, loot list, doctor, etc.
    Subclasses override `title` and `get_text()`."""

    DEFAULT_CSS = """
    _TextResultScreen {
        align: center middle;
    }
    #result-box {
        width: 76;
        height: auto;
        max-height: 24;
        border: thick $secondary;
        background: $panel;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss_screen", "Close")]
    title_text = "Result"

    def get_text(self) -> str:  # pragma: no cover -- overridden
        return ""

    def compose(self) -> ComposeResult:
        with Vertical(id="result-box"):
            yield Label(f"[bold]{self.title_text}[/bold]")
            yield Static(self.get_text(), markup=False)
            yield Static("[dim]Esc to close[/dim]")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)


class RecapScreen(_TextResultScreen):
    title_text = "Recap"

    def __init__(self, box: Box, conn: sqlite3.Connection):
        super().__init__()
        self.box = box
        self.conn = conn

    def get_text(self) -> str:
        from trinity.recap import build_recap, render_recap
        return render_recap(build_recap(self.conn, self.box.id))


class LootListScreen(_TextResultScreen):
    title_text = "Loot recorded"

    def __init__(self, box: Box, conn: sqlite3.Connection):
        super().__init__()
        self.box = box
        self.conn = conn

    def get_text(self) -> str:
        from trinity.loot import list_loot
        items = list_loot(self.conn, self.box.id)
        if not items:
            return "Nothing recorded yet."
        lines = []
        for item in items:
            extra = f" — {item.note}" if item.note else ""
            lines.append(f"{item.kind}: {item.value}{extra}")
        return "\n".join(lines)


class DoctorScreen(_TextResultScreen):
    title_text = "Doctor"

    def get_text(self) -> str:
        from trinity.doctor import render_doctor, run_doctor
        return render_doctor(run_doctor(include_vpn=True))


class LootAddScreen(ModalScreen[None]):
    """Small form: kind + value + optional note. Kept as plain Input
    widgets (not a full form widget library) -- matches this project's
    general "small, hand-rolled, no framework beyond what's needed"
    style elsewhere in the TUI."""

    DEFAULT_CSS = """
    LootAddScreen {
        align: center middle;
    }
    #loot-add-box {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    #loot-add-box Input {
        margin-bottom: 1;
    }
    """

    def __init__(self, box: Box, conn: sqlite3.Connection):
        super().__init__()
        self.box = box
        self.conn = conn

    def compose(self) -> ComposeResult:
        with Vertical(id="loot-add-box"):
            yield Label("[bold]Add loot[/bold]")
            yield Static("[dim]kind: credential | hash | token | flag | other[/dim]")
            yield Input(placeholder="kind", id="loot-kind")
            yield Input(placeholder="value", id="loot-value")
            yield Input(placeholder="note (optional)", id="loot-note")
            yield Button("Save", id="save", variant="success")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "save":
            self.dismiss(None)
            return
        from trinity.loot import add_loot
        kind = self.query_one("#loot-kind", Input).value.strip()
        value = self.query_one("#loot-value", Input).value.strip()
        note = self.query_one("#loot-note", Input).value.strip() or None
        if not kind or not value:
            self.notify("kind and value are both required", severity="error")
            return
        try:
            add_loot(self.conn, self.box.id, kind, value, note=note)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.dismiss(None)


class GtfobinsLookupScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    GtfobinsLookupScreen {
        align: center middle;
    }
    #gtfo-box {
        width: 70;
        height: auto;
        max-height: 20;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="gtfo-box"):
            yield Label("[bold]GTFOBins lookup[/bold]")
            yield Input(placeholder="binary name (e.g. find)", id="gtfo-input")
            yield Static("", id="gtfo-result")
            yield Button("Close", id="close")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        from trinity.gtfobins import lookup
        result = self.query_one("#gtfo-result", Static)
        hit = lookup(event.value.strip())
        if hit is None:
            result.update("No GTFOBins entry for that binary.")
        else:
            result.update(f"{hit.summary}\n\n{hit.source_url}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class HashLookupScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    HashLookupScreen {
        align: center middle;
    }
    #hash-box {
        width: 70;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="hash-box"):
            yield Label("[bold]Hash/token classifier[/bold]")
            yield Input(placeholder="paste a hash or token", id="hash-input")
            yield Static("", id="hash-result")
            yield Button("Close", id="close")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        from trinity.hashes import classify_hash
        result = self.query_one("#hash-result", Static)
        guess = classify_hash(event.value.strip())
        result.update(f"{guess.label}  ({guess.confidence})")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class AdvancedOptionsScreen(ModalScreen[None]):
    """The 'a' key's menu: config-oriented, changes how Trinity
    behaves going forward, not a one-shot action."""

    DEFAULT_CSS = """
    AdvancedOptionsScreen {
        align: center middle;
    }
    #advanced-menu {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss_screen", "Close")]

    def compose(self) -> ComposeResult:
        with Vertical(id="advanced-menu"):
            yield Label("[bold]Advanced Options[/bold]")
            yield ListView(
                ListItem(Label("Switch box mode (educational/professional)"), id="opt-mode"),
                ListItem(Label("Set/change hacker name"), id="opt-hacker-name"),
                ListItem(Label("Generate report now"), id="opt-report"),
                id="advanced-list",
            )
            yield Static("[dim]Esc to close[/dim]")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item_id = event.item.id or ""
        self.dismiss(None)
        app = self.app
        box, conn = app.box, app.conn  # type: ignore[attr-defined]

        if item_id == "opt-mode":
            app.push_screen(ModeSwitchScreen(box, conn))
        elif item_id == "opt-hacker-name":
            app.push_screen(HackerNameScreen(conn))
        elif item_id == "opt-report":
            app.push_screen(ReportModeScreen(box, conn))


class ModeSwitchScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    ModeSwitchScreen {
        align: center middle;
    }
    #mode-box {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    def __init__(self, box: Box, conn: sqlite3.Connection):
        super().__init__()
        self.box = box
        self.conn = conn

    def compose(self) -> ComposeResult:
        with Vertical(id="mode-box"):
            yield Label(f"[bold]Box mode[/bold] (current: {self.box.mode})")
            yield ListView(
                ListItem(Label("educational"), id="mode-educational"),
                ListItem(Label("professional"), id="mode-professional"),
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        from trinity.boxes import set_mode
        mode = (event.item.id or "").removeprefix("mode-")
        set_mode(self.conn, self.box.id, mode)
        self.box.mode = mode
        self.dismiss(None)


class HackerNameScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    HackerNameScreen {
        align: center middle;
    }
    #name-box {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn

    def compose(self) -> ComposeResult:
        from trinity.wizard import get_hacker_name
        current = get_hacker_name(self.conn)
        with Vertical(id="name-box"):
            yield Label(f"[bold]Hacker name[/bold] (current: {current or 'not set'})")
            yield Input(placeholder="new hacker name", id="name-input")
            yield Button("Save", id="save", variant="success")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            from trinity.wizard import set_hacker_name
            name = self.query_one("#name-input", Input).value.strip()
            if name:
                set_hacker_name(self.conn, name)
        self.dismiss(None)


class ReportModeScreen(ModalScreen[None]):
    DEFAULT_CSS = """
    ReportModeScreen {
        align: center middle;
    }
    #report-box {
        width: 50;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    def __init__(self, box: Box, conn: sqlite3.Connection):
        super().__init__()
        self.box = box
        self.conn = conn

    def compose(self) -> ComposeResult:
        with Vertical(id="report-box"):
            yield Label("[bold]Generate report[/bold]")
            yield ListView(
                ListItem(Label("educational"), id="rpt-educational"),
                ListItem(Label("professional"), id="rpt-professional"),
                ListItem(Label("notebook"), id="rpt-notebook"),
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        from trinity.report.data import gather_report_data
        from trinity.report.render import render_report
        mode = (event.item.id or "").removeprefix("rpt-")
        data = gather_report_data(self.conn, self.box.id)
        content = render_report(data, mode)
        self.dismiss(None)
        self.app.push_screen(_ReportOutputScreen(content))  # type: ignore[attr-defined]


class _ReportOutputScreen(_TextResultScreen):
    title_text = "Report"

    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def get_text(self) -> str:
        return self.content


class ShowMeAttestationScreen(ModalScreen[None]):
    """First-use authorization attestation (docs/SHOW_ME_MODE.md §4).
    Shown once, ever, machine-wide -- skipped on subsequent invocations
    once recorded. Deliberately NOT a per-box allowlist, matching the
    CLI's own flow in cli/main.py's show_me_cmd."""

    DEFAULT_CSS = """
    ShowMeAttestationScreen {
        align: center middle;
    }
    #attestation-box {
        width: 70;
        height: auto;
        border: thick $warning;
        background: $panel;
        padding: 1 2;
    }
    """

    def __init__(self, box: Box, conn: sqlite3.Connection):
        super().__init__()
        self.box = box
        self.conn = conn

    def compose(self) -> ComposeResult:
        from trinity.show_me import ATTESTATION_TEXT, has_attestation

        with Vertical(id="attestation-box"):
            if has_attestation(self.conn):
                yield Label("[bold]Show Me Mode[/bold]")
                yield Static("Continuing to milestone selection...")
            else:
                yield Label("[bold yellow]Authorization[/bold yellow]")
                yield Static(ATTESTATION_TEXT)
                yield Button("I understand and agree", id="agree", variant="warning")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        from trinity.show_me import has_attestation
        if has_attestation(self.conn):
            self.set_timer(0.1, self._advance)

    def _advance(self) -> None:
        self.dismiss(None)
        self.app.push_screen(ShowMeMilestoneScreen(self.box, self.conn))  # type: ignore[attr-defined]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        from trinity.show_me import record_attestation
        if event.button.id == "agree":
            record_attestation(self.conn)
            self._advance()
        else:
            self.dismiss(None)


class ShowMeMilestoneScreen(ModalScreen[None]):
    """Pick which single milestone to attempt live."""

    DEFAULT_CSS = """
    ShowMeMilestoneScreen {
        align: center middle;
    }
    #milestone-box {
        width: 60;
        height: auto;
        border: thick $accent;
        background: $panel;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss_screen", "Cancel")]

    def __init__(self, box: Box, conn: sqlite3.Connection):
        super().__init__()
        self.box = box
        self.conn = conn

    def compose(self) -> ComposeResult:
        with Vertical(id="milestone-box"):
            yield Label("[bold]Which milestone?[/bold]")
            yield ListView(
                ListItem(Label("Foothold (get a shell)"), id="ms-foothold"),
                ListItem(Label("Privesc to user"), id="ms-privesc_to_user"),
                ListItem(Label("Privesc to root"), id="ms-privesc_to_root"),
            )
            yield Static("[dim]Esc to cancel[/dim]")

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        milestone = (event.item.id or "").removeprefix("ms-")
        self.dismiss(None)
        self.app.push_screen(ShowMeDisclosureScreen(self.box, self.conn, milestone))  # type: ignore[attr-defined]


class ShowMeDisclosureScreen(ModalScreen[None]):
    """The non-skippable per-invocation disclosure (docs/SHOW_ME_MODE.md
    §7) -- shown every single time, no way to suppress it, matching the
    CLI's own behavior exactly."""

    DEFAULT_CSS = """
    ShowMeDisclosureScreen {
        align: center middle;
    }
    #disclosure-box {
        width: 70;
        height: auto;
        border: thick $secondary;
        background: $panel;
        padding: 1 2;
    }
    """

    def __init__(self, box: Box, conn: sqlite3.Connection, milestone: str):
        super().__init__()
        self.box = box
        self.conn = conn
        self.milestone = milestone

    def compose(self) -> ComposeResult:
        from trinity.agent_harness import detect_agent
        from trinity.show_me import build_disclosure

        agent = detect_agent()
        disclosure = build_disclosure(agent.name if agent else None, self.milestone)
        with Vertical(id="disclosure-box"):
            yield Label("[bold]Show Me Mode[/bold]")
            yield Static(disclosure.banner)
            yield Button("Continue", id="continue", variant="warning")
            yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "continue":
            self.dismiss(None)
            self.app.push_screen(ShowMeRunningScreen(self.box, self.conn, self.milestone))  # type: ignore[attr-defined]
        else:
            self.dismiss(None)


class ShowMeRunningScreen(ModalScreen[None]):
    """Runs Show Me Mode in a background worker (run_show_me blocks on
    real subprocess calls -- must never run on the UI thread) and
    shows the result. This is the screen that actually reflects "watch
    it work" from the disclosure text -- live status updates as
    commands execute, not a silent spinner."""

    DEFAULT_CSS = """
    ShowMeRunningScreen {
        align: center middle;
    }
    #running-box {
        width: 76;
        height: auto;
        max-height: 20;
        border: thick $success;
        background: $panel;
        padding: 1 2;
    }
    """

    BINDINGS = [("escape", "dismiss_screen", "Close")]

    def __init__(self, box: Box, conn: sqlite3.Connection, milestone: str):
        super().__init__()
        self.box = box
        self.conn = conn
        self.milestone = milestone

    def compose(self) -> ComposeResult:
        with Vertical(id="running-box"):
            yield Label("[bold]Show Me Mode — running[/bold]", id="running-title")
            yield Static("Attempting in its own session, not your terminal...", id="running-status")

    def on_mount(self) -> None:
        self._run()

    def action_dismiss_screen(self) -> None:
        self.dismiss(None)

    @work(thread=True, exclusive=True)
    def _run(self) -> None:
        from trinity.show_me import run_show_me

        result = run_show_me(self.conn, self.box.id, self.milestone)
        self.app.call_from_thread(self._show_result, result)

    def _show_result(self, result) -> None:  # noqa: ANN001 -- ShowMeResult, imported lazily above
        title = self.query_one("#running-title", Label)
        status = self.query_one("#running-status", Static)
        if result.outcome == "succeeded":
            title.update("[bold green]Show Me Mode — succeeded[/bold green]")
            status.update(
                f"Recipe to run YOURSELF:\n\n{result.recipe_for_student}\n\n"
                "[dim]This does not count as your own progress until you run it "
                "yourself. The report will mark this milestone as AI-assisted.[/dim]"
            )
        elif result.outcome == "already_known":
            title.update("[bold cyan]Show Me Mode — already known[/bold cyan]")
            status.update(
                f"Trinity already knew this: {result.already_known_title}\n\n"
                f"Recipe: {result.recipe_for_student}\n\n"
                "This wasn't a new capability gap -- the answer was already in "
                "Trinity's knowledge base. Try `next`/`hint`/`explain` again on "
                "this finding."
            )
        else:
            title.update("[bold red]Show Me Mode — no result[/bold red]")
            reason = f" ({result.stop_reason})" if result.stop_reason else ""
            status.update(f"Didn't reach {self.milestone}.{reason}")
