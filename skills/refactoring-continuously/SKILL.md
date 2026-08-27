---
name: refactoring-continuously
description: Restructures existing code without changing its behavior, in small steps verified by passing tests, to pay down design debt as it is found. Use when a change fans out into edits disproportionate to the requirement while the behavior it delivers stays the same, when the same area keeps breaking or keeps resisting new requirements, when an area has become one everyone is afraid to touch, or when code is tidy but its vocabulary no longer matches how the domain is discussed. Do not use as routine cleanup on every edit, as cosmetic modernization, immediately before a release, or to design support for brand-new behavior before any restructuring starts — book that design work with a design skill first.
license: MIT
---

# Refactoring Continuously

## Overview

Maintenance is not a phase; it is how software lives, and design is never done. Every
modification either improves the structure or degrades it — there is no neutral
change. The working ideal: after each change, the system should look as if it had been
designed from the start with that change in mind.

## When to use

- A change feels harder than the size of the requirement justifies, or fans out into
  edits disproportionate to it.
- Recurring symptoms: un-killable bugs, "unexpected" requirements always landing in
  the same spot, code everyone is afraid to touch.
- The code is tidy but its vocabulary no longer matches how the domain is discussed.

**When not to use:** as routine cleanup on every edit — repairing the broken windows
in the path of a change belongs to that change, and an implementation skill covers it;
this skill is for the restructuring that is worth its own tracked task. Not immediately
before a release either: don't destabilize what is about to ship — make the minimal
safe change now and book the refactoring for right after. And never refactor as
virtuosity for its own sake, or as cosmetic modernization — refactor what
understanding has outgrown, not what merely looks old.

## The process

1. **Ask first what the design *should* be** given the requirement that exposed the
   misfit — the structure the code would have if built with that change in mind — and
   refactor toward it as its own behavior-preserving step, rather than patching around
   the misfit. Scope it to the misfit, not a rewrite of the file. Making the behavior
   change alongside is the implementation task and an implementation skill covers it;
   what lands here is the restructuring. If constraints truly forbid it now, do the
   best possible within them and schedule the deferred refactoring visibly.
2. **Never mix refactoring with behavior change.** Have tests green before starting —
   if the code has no tests, first pin its current behavior with characterization
   tests, then move. Take small, deliberate steps (rename, move, extract); run the
   tests after each step; keep the refactoring and the feature/fix as separate
   changes.
3. **Name what you are repairing:** bad names, duplication, misfit structure. The
   broken windows *in the path* of a change belong to that change, and an
   implementation skill repairs them there; this step is for the debt beyond that
   path, which is why it earns a task of its own. If you genuinely cannot fix a piece
   of it now, board it up visibly (a marker, a tracked task) so nobody mistakes
   neglect for acceptance.
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
