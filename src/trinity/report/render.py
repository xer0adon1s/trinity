"""Report renderer seam.

gather_report_data() is the stable contract every renderer reads
from. This registry is the seam FEATURES_BACKLOG asked for so a third
format (notebook markdown, Typst, …) can register without the core
growing another if/else. Both original generators (educational,
professional) keep their existing signatures unchanged.

Not a plugin package system. Just a dict.
"""
from __future__ import annotations

from collections.abc import Callable

from trinity.report.data import ReportData
from trinity.report.educational import generate_educational_report
from trinity.report.notebook import generate_notebook_report
from trinity.report.professional import generate_professional_report

Renderer = Callable[[ReportData], str]

RENDERERS: dict[str, Renderer] = {
    "educational": generate_educational_report,
    "professional": generate_professional_report,
    "notebook": generate_notebook_report,
}


def render_report(data: ReportData, mode: str) -> str:
    renderer = RENDERERS.get(mode)
    if renderer is None:
        known = ", ".join(sorted(RENDERERS))
        raise ValueError(f"Unknown report mode {mode!r}. Known: {known}")
    return renderer(data)
