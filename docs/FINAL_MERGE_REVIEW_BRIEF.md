# Final merge review — the MERGED main branch, not either individual half

This is the last check before Alexander (the CEO) does a live alpha
test on a real HTB/CTF box. Two branches (`fix1-fix4-claude`:
sharing.py/intake.py/db.py fixes, and `fix2b-fix3-fix6-cursor`: CI/
lint/docstrings/TUI fixes/smoke tests) were independently implemented,
cross-reviewed by each other and by Doc, polished based on that
feedback, and merged into `main` with zero conflicts (they touched
disjoint files). Every individual half has already been reviewed
multiple times. Nobody has reviewed the MERGED result as a whole.

This is what you're checking for, specifically:

1. **Interaction bugs.** Each half was correct in isolation, verified
   in its own worktree — but do the two halves interact badly now that
   they're both live in the same tree? E.g.: does anything Fix 3/6
   touched (docstrings, TUI, doctor timeouts) assume something about
   `db.py`/`sharing.py`/`intake.py` that Fix 1/4 changed? Does the
   ruff/mypy config (added by the Cursor half) actually stay clean
   against the FINAL merged Fix 1/4 code (not the version it was
   written against before the polish pass added 11 more registered
   tables and the frozenset change)?
2. **Anything a merge could have silently broken** even with zero
   git conflicts -- e.g. two independent changes to overlapping runtime
   behavior that don't conflict textually but do conflict logically.
3. **Whether the full test suite result (499 passing) is telling the
   whole story** -- spot check a few of the tests added by each side to
   confirm they're actually exercising real behavior post-merge, not
   just passing by coincidence.
4. **Anything from the ENTIRE session's work (not just these two
   branches) that could bite a live tester on a real box RIGHT NOW.**
   You have full read access to the whole repo and its history --
   `git log --oneline` back through the session's earlier quarantine
   and review commits is fair game if something looks off. The bar
   here is genuinely different from the prior reviews: Alexander is
   about to run this against a REAL machine, not a simulated/dev
   environment. Practical concerns like "does this assume Linux," "is
   there a crash path in the normal wizard->watch->done flow," "does
   the CI config reference anything that doesn't exist" matter more
   right now than architectural elegance.

## What NOT to do

- Do not re-relitigate Show Me Mode -- it's quarantined and out of
  scope; if you notice anything new about it, note it as a quarantine
  checklist addition, not a blocker.
- Do not re-run the full four-round design review process. This is one
  focused pass on the merged result.
- This is READ-ONLY: do not edit code under src/ or test/. If you find
  something you'd fix in 2 minutes, say so in the review rather than
  fixing it -- Doc will triage.

## Format

Same three-category taxonomy as the last cross-review round:

```
## Bugs / real risks for a live tester
(numbered, file/line evidence, severity, and specifically flag if it's
NEW from the merge interaction vs. pre-existing)

## Design questions
("curious why..." -- legitimate on its own, doesn't need to be a bug)

## Things confirmed solid
(what you checked and found genuinely correct -- be specific about
what you verified, not just "looks fine")

## Verdict
Is `main` as it stands right now safe for Alexander to run a live
alpha test against a real box? Yes / yes-with-caveats / no. If
caveats, list them as a short, concrete pre-flight checklist.
```

Write to `findings/final_merge_review_cursor.md` and commit on this
branch (`final-merge-review-cursor`). Do NOT merge or push.

Run `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy src/`
against this actual merged tree first as your baseline before diving
into code reading.
