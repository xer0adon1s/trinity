Final code-review-for-polish pass: Trinity's Voice v1

Context: you graded the first cut of this implementation (your grade
is in findings/voice_grade_{cursor,claude}.md from the previous round,
still in git history on branches voice-grade-{cursor,claude} if you
want to diff against your own findings). Every real bug either of you
found has been fixed on `main` in commit 69865e5 ("fix: address
Trinity's Voice v1 grading findings"). This is a group-project polish
round, not a re-grade -- the goal is to catch anything left before
this ships to Alexander's live alpha test, and to genuinely improve
anything that's merely okay rather than good.

Read (in this order):
1. docs/TRINITY_VOICE_DESIGN.md -- the design doc, now updated to
   match what's actually built (v1 = authored corpus + deterministic
   renderer, no live AI; v2 = deferred).
2. `git show 69865e5` -- the exact fix commit, so you know what
   changed since your grade and can verify each fix is real, not
   just claimed.
3. src/trinity/voice.py, src/trinity/voice_seed.py -- the module and
   its authored corpus.
4. src/trinity/tui/dashboard.py's `_render_result` and `_handle_file`
   -- the integration point.
5. test/unit/test_voice.py and the Voice-related tests in
   test/unit/test_dashboard.py.

What to check:
- Are the 4 bug fixes from the grading round actually correct, not
  just plausible? Run the code yourself if you're not sure -- don't
  trust the commit message.
- Any remaining bugs, however small, in the Voice module or its
  dashboard integration?
- Is the authored corpus content itself good? You're not a security
  reviewer here, you're a teaching-quality reviewer -- read each of
  the 6 entries in voice_seed.py and judge them the way Alexander
  would: witty-but-implied personality (never literally naming "the
  Matrix" anywhere, not even in a code comment), consistent structure,
  genuinely teaches something transferable in the 4th paragraph (not
  just restating the finding), no spoilers of later attack phases.
  Call out anything you'd genuinely rewrite.
- Test coverage: any gap you'd want closed before this ships?
- Anything about the design doc's documented scope cuts (always-
  inline not expandable, TUI-only, the finding_explanations naming
  collision flagged for v2) that concerns you or that you'd resolve
  differently?
- "I'm curious why you did it this way" questions are welcome and
  wanted here even without a concrete bug attached -- Alexander
  explicitly asked for this kind of review, not just bug-hunting.
- Specific praise for things done well is also wanted, not just
  criticism -- if something is a genuinely good pattern, say so and
  say why, so it gets reused elsewhere in the codebase deliberately
  rather than by accident.

Do NOT write or edit code in this pass -- this is review only. Write
your findings to findings/voice_polish_review_{cursor,claude}.md
(use your own name) and commit on your branch. Do not merge or push.

If you find something you'd fix, describe the fix concretely enough
that the next pass (which will be a real implementation pass, likely
you again) can act on it without re-deriving it from scratch.
