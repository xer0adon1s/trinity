# Cross-review brief — review the OTHER implementer's actual code

This is a peer code review of real, merged-locally implementation work
(not a design review this time). You are reviewing work done by a
different AI coding agent on a parallel branch of the same project,
implementing a different half of an agreed fix plan. Full context: the
project is Trinity, a CTF/HTB training tool heading toward a 1.0 the
CEO will personally user-test. Four rounds of review already happened
before either of you wrote code (two full-program reviews, a fix-plan
peer review, and a design cross-talk round) -- this round is checking
the actual diffs that resulted.

## Important: this is not just a bug hunt

Alexander (the CEO) explicitly asked for a broader kind of review than
pass/fail. Three categories of finding are all equally welcome and
equally valuable:

1. **Bugs** — something that is factually broken: wrong logic, a test
   that doesn't test what it claims, a regression, a case that will
   crash or silently misbehave.
2. **Design questions** — "I'm curious why you did it this way" is a
   completely legitimate finding on its own, even with no bug attached.
   If you look at a choice and think "that's unusual, I wonder if
   there's a reason" -- say exactly that. You don't need to be sure
   something is wrong to flag it. A question you're not certain about
   is more useful reported than suppressed.
3. **Genuine praise** — if something is well done, say so plainly. This
   isn't a courtesy score; it's useful signal about which patterns to
   reuse.

Do not force every observation into "bug" or "not a bug." A three-way
taxonomy (bug / question / praise) produces a much more useful report
than a binary one.

## What to review

You are reviewing the git history on the branch checked out in this
worktree, from commit `466c560` to `HEAD` — run `git log --oneline
466c560..HEAD` and `git diff 466c560..HEAD` to see exactly what
changed. Read the brief that guided this implementation
(`docs/IMPLEMENTATION_BRIEF_CLAUDE.md` or
`docs/IMPLEMENTATION_BRIEF_CURSOR.md`, whichever matches this branch)
to understand what was supposed to be built, then judge the actual
code against it — not against your own preferences for how you'd have
done it, though noting "I'd have done X differently, curious why you
chose Y" is exactly the kind of question category above.

Also check: does `uv run pytest -q` still pass? If ruff/mypy are
configured on this branch, do those pass too?

## Format

Write your review to `findings/crossreview_<you>_on_<them>.md` (e.g. if
you are Claude reviewing Cursor's branch:
`findings/crossreview_claude_on_cursor.md`). Structure:

```
## Bugs found
(numbered, with file/line evidence, severity)

## Design questions
(numbered, with file/line reference, phrased as genuine questions —
"why did you choose X over Y here?" not "you should have done Y")

## Things done well
(brief, specific — not generic praise)

## Summary verdict
(would you merge this as-is, with minor fixes, or does it need real
rework — and why)
```

This is READ-ONLY: do not edit any code in this worktree. Commit your
review file on the current branch when done. Do NOT merge or push.
