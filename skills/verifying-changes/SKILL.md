---
name: verifying-changes
description: Use when work is believed complete — before merging, releasing, or reporting success — when reviewing someone else's diff, pull request, or design document, when planning or judging the tests for a change, or when deciding whether "all tests pass" is enough to ship.
---

# Verifying Changes

## Overview

Everything humans (and agents) make is flawed; verification is the deliberate experiment that finds the flaws before users do. Review exists to find what the author could not see: defects, hidden complexity, wrong assumptions, and gaps between what was asked and what was built. The reviewer's verdict on clarity is authoritative — if a reader finds code complex or nonobvious, it *is*, whatever the author intended. Test ruthlessly and automatically: find the bugs now so users don't find them later, and make sure no human ever has to find the same bug twice. And know the limit: no amount of verification validates the *objectives* themselves — whether this is what users actually need must be checked against reality separately.

Review reports findings; it does not rewrite the work. Keep the roles separate.

## When to Use

- A change is "done" and someone wants to merge, ship, or report success.
- Reviewing a diff, branch, pull request, or design document — your own work before submitting, or someone else's.
- Verifying an implementation against its spec or plan.
- Designing, or judging the adequacy of, the tests for a change.
- A bug was just fixed and the temptation is to move on.

## The Reviewer's Stance

- **Study before discussing.** Read the actual artifacts — the diff, the code, the tests — alone and carefully before forming conclusions. Summaries and slide-ware hide the embarrassing details; the source does not.
- **Right thing before thing right.** First ask whether this solves the actual need — the most expensive failures are competent implementations of the wrong thing. Then ask whether it is built soundly.
- **Assume competence, then verify.** For each surprising choice ask "what would make a smart person do this?" — the answer reveals a constraint you missed or a real defect, and both are findings. Verify claims against the code and by running things; never accept "it works" without knowing why it works.
- **Widen the perspectives.** Review with viewpoints beyond the author's: maintenance, testing, and user-side concerns each catch different defects, and one reviewer's spoken concern triggers another's. Reviewing alone, make those passes explicitly: read the diff once as its future maintainer, once as its tester, once as its user.
- **Make the author argue correctness.** Have the author explain *why* the change is correct while you challenge the argument and its assumptions — scrutiny of reasoning catches what tests cannot. Reviewing your own work, write the argument down and attack it.
- **Fix the problem, not the blame.** Findings are about the work. Report them with evidence — a failing input, a scenario, a measured number — not adjectives.
- **The design is at fault, not the reader.** When you must reread something to understand it, that is a finding (obscurity), even if it turns out to be correct.

## Review Layers

Work through these in order; each layer's findings can moot the ones below.

1. **Intent** — Does the change do what was asked? Walk each requirement/scenario through the code. Look for silent scope changes: requirements dropped without discussion, or unrequested behavior added.
2. **Assumptions** — What must be true of the environment, inputs, concurrency, and scale for this to work? Are those assumptions documented, checked, and actually true?
3. **Design** — Apply the red-flag checklist below. Would a different decomposition remove whole classes of problems? Propose the alternative, don't just note the smell.
4. **Correctness** — Boundary conditions, off-by-ones, ordering, concurrency, resource lifecycles. Hunt hardest in error paths: incorrect error handling is one of the most common causes of catastrophic failure. Check every handler: can it execute? does it swallow something a caller needs? does cleanup happen on every exit path?
5. **Tests** — Do tests verify the *contract*, including boundaries and failure modes, or just rehearse the happy path? Would they catch the bugs you almost believed were there? Is every previously found bug pinned by a test?
6. **Docs and comments** — Do interface comments match behavior? Did the change invalidate any comment, document, or example it didn't update? Is there leftover debug code? Duplicated knowledge that has already drifted apart is a defect twice over.

## Red-Flag Checklist

| Red flag | What to look for |
|---|---|
| Shallow module | Interface nearly as complex as the implementation it fronts |
| Information leakage | The same design decision (format, schema, protocol) known to several modules |
| Temporal decomposition | Code structure mirroring execution order instead of knowledge |
| Overexposure | Common operations forcing callers to learn rare features |
| Pass-through method | Adds no behavior; signature relayed one level down |
| Duplication | Nontrivial code or knowledge represented more than once |
| Special–general mixture | A general mechanism containing code for one specific caller |
| Conjoined code | Can't understand one method without reading another |
| Comment repeats code | The comment adds nothing the next line doesn't say |
| Implementation in interface docs | Callers forced to learn internals to use the thing |
| Vague or overloaded name | One name meaning different things in different places |
| Hard to describe | The accurate doc-comment would have to be long and convoluted |
| Nonobvious code | Meaning not clear on a careful first read |
| Structure-chaining | `a.getB().getC().doD()` — coupling to structure the caller doesn't own |
| Coincidental correctness | It passes, but nobody can say why; undocumented behavior relied upon |
| Swallowed error | Caught, logged, and limped past a state the program can't handle |
| Unbalanced resource | Acquire and release in different places, or missing on an exit path |
| Anemic domain object | Data bags with all behavior drained into service code |
| Buried rule | A business rule expressed only as an inline conditional, not a named concept |
| Language drift | Code vocabulary diverging from how the domain experts speak |
| Broken windows | Known-bad code left standing, inviting more of the same |
| Manual procedure | A human performing repeatable steps a script should own |

## Testing the Change

Judge (and, when asked, build) tests along these dimensions. Climb them in order: with units verified first, an integration failure points at the integration.

- **Unit against contract** — each module honors its stated promises across the full input range: boundaries, empty/zero cases, maximum sizes, invalid input.
- **Integration** — do modules honor the contracts *between* them? This is the single largest source of bugs after unit level.
- **Validation** — is it the answer to the right question? A bug-free implementation of a misunderstanding is still a failure. Use realistic usage patterns, not just synthetic ones — and synthetic data for volumes and boundaries real data won't hit (leap days, huge records, empty inputs, presorted input).
- **State coverage over line coverage** — executing every line proves little; enumerate the meaningful states and transitions and cover those. Derive the states from the contract: input classes × boundary conditions × failure modes. Hitting 100% lines with happy-path data is false confidence.
- **Failure and exhaustion** — behavior when memory, disk, connections, or time run out; does it fail early, loudly, and without corrupting data?
- **Performance** — measured under realistic load, against stated targets, not intuition.
- **Test the tests** — deliberately introduce a defect (locally, discard after) and confirm the suite catches it; a suite that has never been seen to fail is decoration.
- **Regression permanence** — every bug found by a human gets an automated test *before* it is fixed, so no human finds it twice.
- **One command** — the whole suite must run automatically with every build, results interpreted automatically; tests that need manual setup won't be run.

Hard-to-test code is itself a finding: if exercising a unit drags in half the system, the coupling is the defect.

## Writing Up the Review

Deliver a structured report (store it wherever the project keeps review records, or reply inline where the review was requested):

1. **Verdict** — one of: approve / approve with fixes / needs rework, with a one-paragraph justification.
2. **Findings** — ordered by severity:
   - *Must fix*: incorrect behavior, spec violations, data loss/corruption risks, swallowed errors.
   - *Should fix*: design red flags, missing tests, obscurity that will tax every future reader.
   - *Consider*: simplifications, naming, consistency nits.
   Each finding: location, the defect in one sentence, the evidence (failing scenario or concrete consequence), and where useful a sketched alternative.
3. **Questions** — assumptions you could not verify; direct these to the author rather than guessing.
4. **What is good** — name the load-bearing strengths so they survive the rework.

Be as rigorous with your own work as with a stranger's: run the checklist on your own diffs before declaring them done, and never soften a finding because the fix is inconvenient.

## Common Mistakes

| Mistake | Correction |
|---|---|
| Reviewing only the diff lines | Read the surrounding code; the bug is often in what the diff *didn't* change |
| Style nits drowning out real defects | Order findings by severity; automate style enforcement instead of reviewing it |
| "Tests pass" treated as proof | Ask what the tests would have caught; check states, boundaries, and error paths |
| Fixing a bug and moving on | Add the test that traps it *before* the fix; no one should find the same bug twice |
| Reporting success before verification has run | Run it and read the output first; evidence precedes claims |
| Accepting complexity as inevitable | If it's hard to read, say so; the reader's judgment is the ground truth |
| Criticism without alternatives | For design findings, sketch at least a direction for the fix |
| Verifying the goals were met, never the goals | Also ask whether the stated goals still match the actual need |

## Common Rationalizations

| Excuse | Reality |
|---|---|
| "It works on my machine" | Prove it where it will actually run, with real data. |
| "Trivial change — skip the tests/review" | Trivial changes break systems; verifying trivia is cheap. |
| "Coverage is 90%, we're done" | Line coverage is not state coverage; the untested states are where it bites. |
| "The author is senior, it's fine" | Experts fail big: they confidently build the wrong thing. |
