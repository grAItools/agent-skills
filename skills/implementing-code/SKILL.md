---
name: implementing-code
description: Use when writing or modifying source code — implementing a planned feature, fixing a defect, refactoring, or extending an existing codebase — to produce code that is correct, obvious to readers, and safe to change.
---

# Implementing Code

## Overview

Working code isn't enough. Every change either improves or degrades the design, and complexity accumulates in small, individually defensible steps — so the finish line is "the design is good *and* it works," never just "it works." Program strategically: invest continually in structure, comments, and tests as part of every task, not as cleanup deferred to a mythical quiet week. Optimize for the reader: code is read far more often than written, and its clarity is judged by readers, not by its author.

## When to Use

Any time you write or modify production code: features, bug fixes, refactors, extensions. For designing the structure first, use a design skill; for verifying the result, use a review skill.

## Before Writing

- **Understand before changing.** Read the surrounding code until you can say why it works, not just what it does. Never modify code whose behavior you can't explain — and never ship generated or copied code you don't understand line by line.
- **When in Rome.** Before deciding anything in an existing codebase, look for the established convention — names, style, interfaces, error handling, test placement — and follow it. Don't "improve" a convention unless you are prepared to migrate every existing use; local inconsistency costs more than the improvement is worth.
- **Ask what the design should be.** Given the new requirement, what structure would this code have if it had been designed with the change in mind from the start? Refactor toward that, then make the change — rather than bolting the feature onto the old shape. The unit of growth is an abstraction, not a feature.
- **Don't program by coincidence.** Rely only on documented behavior of libraries and APIs. If something works and you don't know why, stop and find out — it may not really work. Document any assumption you are forced to make, and back it with an assertion.

## Interfaces and Comments First

Write the interface before the body: the signature plus a comment stating the abstraction — behavior as the caller perceives it, each parameter and return value precisely, side effects, preconditions, error cases. Then implement.

- Comments capture what code cannot express: intent, rationale, units, bounds, meaning of null/empty, ownership of resources, invariants. A comment that restates the adjacent code is noise — write at a different level than the code: more precise (for declarations) or more abstract (for interfaces and blocks).
- Keep implementation details out of interface comments; keep the *why* of tricky code in implementation comments, at the code, not in the commit message — future readers see the code, not the log.
- **Difficulty writing the comment is a design signal.** If a method or variable is hard to describe simply and completely, the entity is badly designed. Fix the design, don't wordsmith the comment.

## Naming

- Precise, unambiguous, consistent: one name per concept, one concept per name, everywhere in the system. Two different things sharing a name is how six-month bugs are made.
- Use the domain's vocabulary. Name booleans as predicates. Longer names for wider scopes; generic loop indices only where the whole scope is visible.
- If a precise, simple name won't come, the design underneath is unclear — refactor the entity instead of forcing a name.

## Structure Rules — Quick Reference

| Rule | Practice |
|---|---|
| One authoritative home per fact | Never copy-paste nontrivial code or duplicate knowledge; extract, or generate one form from the other |
| Write shy code | A method calls only its own object, its parameters, objects it creates, its direct components — never chains like `a.getB().getC().doD()` |
| No hidden coupling | No mutable globals; pass context explicitly; no dependence on call order or hidden static state |
| Separate commands from queries | Queries compute without observable side effects; commands change state and return nothing of substance |
| Prefer immutable values | Push complex logic into immutable value types whose operations return new values — safe to share, easy to test |
| Deep functions over short ones | Split a function only when the piece is separately understandable; if reading one half requires the other, rejoin them |
| Make the common case simple | Defaults for everything; rare options invisible to those who don't need them |
| Choose representations that erase edge cases | e.g. an empty range instead of a "no selection" flag — the normal-case code then handles the edges |
| Composition over implementation inheritance | Inherit interfaces for polymorphism; reuse implementation via helpers, not base-class entanglement |

## Defensive Discipline

- **Design by contract.** Decide each routine's preconditions, postconditions, and invariants. Be strict in what you accept, promise little, and treat a violated contract as a bug — never as a condition to limp past.
- **Assert the impossible.** Wherever you think "this can't happen," check it. Assertions must be side-effect free and stay enabled in production; they are for impossibilities, never for expected conditions like user input.
- **Crash early.** A dead program does far less damage than a crippled one writing corrupt data. On an impossible state, stop as soon as cleanly possible. Every switch gets a default that complains; every "can't fail" call gets checked.
- **Exceptions are for the exceptional.** If the code would still make sense with all handlers removed, exceptions are being used for normal control flow — use return values for expected outcomes. Better still, redefine operations so the exceptional case is normal, well-defined behavior (deleting an absent entry succeeds; querying an empty set returns empty).
- **Balance resources.** Whatever allocates a resource deallocates it, visibly, in the same place; release in reverse order of acquisition; acquire shared sets in one fixed order; use scope-bound cleanup (destructors, finally, context managers) so early exits can't leak.
- **Never swallow errors callers need.** Handle what you can at the lowest level; let the rest propagate to one aggregate handler — silently eating an error converts a visible failure into data corruption.

## Tests With the Code

- Write the test with (or before) the code, against the contract: does the routine do what it promises, over the full range including boundaries? Testing against the contract also tests whether the contract means what you think.
- Prefer covering meaningful *states* — boundaries, emptiness, overflow, ordering, concurrency — over merely executing lines.
- Every test must run with one command, and the full suite with every build. Coding isn't done until all the tests run.
- When fixing a bug, first write a failing test that reproduces it, then fix. Once a human finds a bug, a test finds it forever after.
- Promote every useful debugging probe into the permanent suite.
- Hard-to-test code is the design complaining: if a unit test drags in half the system, decouple before proceeding.

## Modifying and Refactoring

- **Fix broken windows.** Bad names, dead code, misleading comments, duplicated snippets: repair them when you find them, or visibly quarantine them — one tolerated mess licenses the next.
- Refactor in small steps, each verified by the test suite; never mix refactoring with behavior change in the same step. No tests? Write characterization tests first.
- Leave every file you touch a little better than you found it. If a needed refactoring is too big for now, schedule it explicitly — silent deferral is how debt becomes permanent.
- Before committing, diff-scan: every change reflected in comments and docs, no leftover debug code, no accidental behavior change.

## Performance

- Know the rough cost of expensive operations (network round trips, disk I/O, allocation, cache misses) and pick the naturally efficient design when it's equally simple.
- Otherwise: simple first, then measure. Never optimize on intuition; measure before, measure after, and revert changes that don't produce a real, needed speedup. For genuinely hot paths, design the minimal ideal critical path and keep special cases off it behind a single up-front test.
- Note the expected input sizes for every loop and recursion; make sure the growth order is sensible for realistic n before shipping.

## Definition of Done

- [ ] Behavior matches the plan/spec; deviations were raised, not silently absorbed.
- [ ] All tests pass, including new tests for the new behavior and its boundaries.
- [ ] Interfaces have accurate contracts; comments describe what the code cannot.
- [ ] Names are precise and consistent with the codebase and domain vocabulary.
- [ ] No duplicated knowledge, no swallowed errors, no leaked resources.
- [ ] The design in the touched area is better — or at minimum no worse — than before.
- [ ] Repeated manual steps you performed are scripted for the next person.

## Red Flags — Stop and Reconsider

- "It works, ship it" — without knowing *why* it works.
- Copy-pasting a block and editing it slightly.
- A comment that repeats the code, or a comment you struggled to write simply.
- A function you can't name precisely.
- Catch blocks that log-and-continue past states the program can't actually handle.
- A test that needs elaborate setup of unrelated subsystems.
- "I'll clean it up after the deadline" — there is always another deadline.
