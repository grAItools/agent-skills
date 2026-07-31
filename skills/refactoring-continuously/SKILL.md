---
name: refactoring-continuously
description: Use when touching existing code for any reason, when a seemingly small change requires edits in many places, when the same area keeps breaking or keeps resisting new requirements, or when code is tidy but its vocabulary no longer matches how the domain is actually discussed.
---

# Refactoring Continuously

## Overview

Maintenance is not a phase; it is how software lives, and design is never done. Every
modification either improves the structure or degrades it — there is no neutral
change. The working ideal: after each change, the system should look as if it had been
designed from the start with that change in mind.

## When to use

- Before and during any fix or extension of existing code.
- A change feels harder than the size of the requirement justifies.
- Recurring symptoms: un-killable bugs, "unexpected" requirements always landing in
  the same spot, code everyone is afraid to touch.

**When not to use:** immediately before a release — don't destabilize what is about to
ship; make the minimal safe change now and book the refactoring as a tracked task for
right after. And never refactor as virtuosity for its own sake — refactor what
understanding has outgrown, not what merely looks old.

## The process

1. **Ask first what the design *should* be** given the new requirement — the structure
   it would have if built with this change in mind — then refactor toward that and
   make the change, rather than patching around the misfit. Scope it to the code your
   change actually touches — the target is the misfit in your path, not a rewrite of
   the file. If constraints truly forbid it now, do the best possible within them and
   schedule the deferred refactoring visibly.
2. **Never mix refactoring with behavior change.** Have tests green before starting —
   if the code has no tests, first pin its current behavior with characterization
   tests, then move. Take small, deliberate steps (rename, move, extract); run the
   tests after each step; keep the refactoring and the feature/fix as separate
   changes.
3. **Fix broken windows on contact:** bad names, duplication, misfit structure. If you
   genuinely cannot fix one now, board it up visibly (a marker, a tracked task) so
   nobody mistakes neglect for acceptance.
4. **Watch the deeper signals — refactor on model grounds, not just code smells:**
   - *Change amplification:* one conceptual change requires edits in many places.
   - *Wrong-model churn:* requirements that "don't fit" keep arriving at the same
     spot; a bug refuses to die despite repeated fixes.
   - *Language drift:* the code's vocabulary no longer matches the terms the domain's
     people actually use — tidy code can still express the wrong model.
   These signals call for finding the missing or misplaced concept. A short, focused
   exploration with people who know the domain beats solo redesign.
5. **Don't demand a full cost-benefit case for every improvement.** If you wait until
   the change can be completely justified, you have waited too long: the visible costs
   (developer time, risk of touching code) are always argued against invisible ones
   (the tax the misfit levies on every future change). Default toward refactoring
   whenever understanding has outgrown the design.
6. **Expect punctuated equilibrium.** Long steady refinement is occasionally
   interrupted by a breakthrough in which a better model makes complexity evaporate. A
   sudden sense that the current model is broken usually means understanding has
   reached a new level — treat the crisis as the opportunity it is.

## Red flags

- "Just the one-line patch" applied inside a known tangle, with no tracked follow-up.
- A refactoring buried inside a feature or bugfix diff.
- Improvements blocked pending "full justification".
- A module everyone routes around instead of touching.
- Renames skipped after the team's vocabulary changed.
- "We'll clean it up after the release" — with no scheduled, visible task.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "No time now; we'll clean up later" | The next crunch is already coming. Book the refactoring visibly or do it now. |
| "It works — don't touch it" | Working is not healthy; the tangle taxes every future change. |
| "A refactor is too risky" | Small tested steps are not a rewrite; unbounded decay is the real risk. |
| "The tests will catch any problem" | Only if they exist. Put tests in place first, then move. |
