---
name: discovering-requirements
description: Use when starting work on a new feature, product idea, defect report, or vague request — before any design or coding — or when a request's purpose, users, or scope are unclear, contested, or stated as a solution ("add a button", "we need a dashboard") rather than as a need.
---

# Discovering Requirements

## Overview

Requirements are not collected — they are dug out from under layers of assumptions, misconceptions, and politics, and they keep changing as everyone's understanding grows. The hardest part of building software is deciding precisely what to build; a chief service of whoever does this work is helping the requester discover what they really want. Treat requirements work as iterative discovery done *with* the people who have the need. The deliverable is a small, weighted, explicitly shared understanding of the **need**, written down — not a solution specification, not a design, not code.

A requirement is a statement of something that needs to be accomplished. It is not an architecture, not a design, and not a user interface.

## When to Use

- A new feature idea, product concept, or "what if we..." conversation.
- A defect or pain report whose underlying need is unclear, or that implies a behavior change (what *should* it do, and for whom?).
- A request that arrives as a solution ("add a button that...", "we need a dashboard") rather than as a need.
- Before writing any design or plan for non-trivial work.

Do not use for mechanical, fully specified changes (rename X, bump a version) where the need is unambiguous — though even then, state the why in one sentence.

## How to Work

**Dig, don't transcribe.** For every stated requirement, ask why it is needed and what the requester does today. Stated requests are often workarounds for a deeper need — and the need behind a solution-shaped ask is often cheaper to satisfy than the ask itself. Discover the underlying reason users do a thing, not just the way they currently do it, and record the *why* — it informs a thousand later implementation decisions.

**Work with a user to think like a user.** Direct contact with real users and domain experts beats profiles, tickets, and second-hand summaries. Watch how the work is actually done — if possible, do it yourself for a while; the most valuable facts are the ones nobody thinks to mention. When direct access is impossible, route the questions through whoever made the request, and mark which answers are facts and which are assumptions.

**Ask one focused question at a time.** Put forward a concrete question with a recommended answer and the reasoning behind it, then iterate on the response. It is easier to criticize something concrete than to create from nothing, so concrete proposals draw out unspoken needs that open-ended surveys never surface.

**Separate need, policy, and interface.**

| Kind | Example | Where it belongs |
|---|---|---|
| Need | "Only authorized users may view an employee record" | The requirement itself — abstract, stable |
| Policy | "Supervisors and HR staff are authorized" | Documented separately; expect it to become configuration or data, not hard-coded logic |
| Interface preference | "Use a dropdown for the term" | A requirement only if users genuinely cannot accept anything else |

Keep each requirement as the simplest abstract statement that accurately reflects the business need. Abstract means solution-free, not vague: requirement statements never prescribe architecture, design, or UI, but the facts inside them stay concrete. Abstractions live longer than details.

**Build the shared vocabulary.** Agree on precise names for the domain concepts with the people who know the domain, and use those exact terms in every question, scenario, and document — and later in the code. Maintain a glossary. When a term feels awkward in conversation, the underlying concept is probably wrong: fix the concept, then the name — a change of term is a change of understanding. If the experts can't follow your restatement of their domain, the fault is in your model, not in them. Projects fail when people call the same thing by different names, or different things by the same name.

**Write the user model down — better wrong than vague.** State explicitly who the users are, what they know, what they are trying to accomplish, in what environment, and how the user classes are weighted against each other. Where facts run out, guess concrete values and publish them labeled as guesses so they can be attacked: a wrong explicit assumption gets questioned and corrected; a vague unspoken one silently steers every downstream decision. Without an explicit shared model, each contributor designs for a different imagined user and coherence is lost.

**Weight and prune.** A flat, unweighted wish list is a failure mode: it accretes because agreeing costs less socially than ranking. Force a ranking — essential, desirable, out of scope — and record what was deliberately excluded. Someone must advocate for the product as a whole (its coherence, economy, robustness) against the union of everyone's wishes; take that role if nobody else has it. Trace every detailed requirement back to a top-level goal, and delete the ones that cannot be traced.

**Surface the constraints and the scarce resource.** List all known constraints explicitly: deadlines, compatibility, regulation, capacity, environment. Audit each one — real, obsolete, misperceived, or self-imposed? Re-scan the list periodically: sometimes the breakthrough is noticing a constraint has disappeared, not designing around it. Identify the one scarce resource the design will have to ration (latency, memory, screen space, attention, schedule — often not money) and name it. When handed an implementation as a requirement ("must use technology X", "must have this topology"), push back and ask what *property* it is meant to achieve: specify properties, never means.

**Capture behavior as goal-driven use cases.** Write concrete usage scenarios: the actor and their goal in context, preconditions, the success and failure end conditions, the main success scenario, the important variations and failure paths, and expected frequency. Include boundary cases and the unglamorous realistic cases. Walk each scenario aloud with the domain experts — awkwardness you can hear is a misunderstanding you have not yet found. Scenarios double as acceptance criteria and, later, as tests. Even low-frequency scenarios can expose requirements nobody knew existed, so walk more of them than feels necessary.

**Make quality a requirement.** Agree explicitly on how good is good enough — performance, reliability, polish — with the people who will use the result. Great software today is often better than perfect software later; scope and quality belong in the requirements, not in silent assumptions.

**Know when to stop.** Ever-more-detailed specification hits diminishing, then negative, returns: no document captures every nuance, and an over-detailed spec robs later stages of the discoveries they will make. When further description stops adding shared understanding, stop describing — answer the remaining questions with a prototype or a thin working slice instead. Requirements, design, and implementation are facets of one process; expect implementation to feed corrections back into the spec, and welcome them.

**Track change.** Requirements will keep arriving after agreement — designing and prototyping elicit requirements nobody could state up front. That is normal and healthy; welcome them rather than suppressing them as scope churn. But record each addition, who asked for it, and its cost in schedule and complexity, so "just one more feature" is a visible decision rather than silent drift.

## The Specification

Produce a single concise document (store it wherever the project keeps such documents; if there is no convention, ask or propose one), scaled to the stakes — a page can be enough for a small feature:

1. **Goal** — one paragraph: the need and the value, in domain language.
2. **Users** — the explicit user model, with weightings and labeled guesses.
3. **Needs** — ranked; with an explicit out-of-scope list.
4. **Constraints** — audited, each marked real / assumed; the scarce resource named.
5. **Scenarios** — main success paths, key variations and failures.
6. **Policies** — changeable business rules, kept separate from the needs.
7. **Glossary** — the agreed vocabulary.
8. **Open questions** — what remains unknown, and how each will be resolved.

Mark the document DRAFT until the stakeholders have confirmed it reflects their need and you can state the ranked top goals, name the users and their why, and walk one main success scenario without open contradictions; only then mark it AGREED and move on to design. Further certainty comes from prototypes and increments, not from more prose.

## Red Flags

| Symptom | What it means |
|---|---|
| Unweighted wish list | Nobody advocates for the whole; ranking was avoided |
| Vague user model | Every contributor is designing for a different imagined user |
| A solution stated as a need | The real need is still buried; dig |
| Policy baked into a requirement | Change will require code edits instead of configuration |
| A constraint nobody can justify | Possibly obsolete or misperceived; audit it |
| Vocabulary drift between talk and documents | The shared model is fragmenting |
| Spec growing while understanding isn't | Specification spiral; switch to a prototype |
| Scope additions with no recorded cost | Drift is being absorbed silently |
| Requirements declared "frozen" | Discovery continues through design and delivery; freezing hides the churn instead of managing it |

## Common Rationalizations

| Excuse | Reality |
|---|---|
| "The ask is clear — just build it" | The stated ask is a guess at a solution. The need behind it is often cheaper to satisfy. |
| "Users don't know what they want" | True — that is why you prototype and iterate *with* them, not why you skip them. |
| "We'll figure it out while coding" | Detail discovery during design is healthy; starting without weighted goals is not. |
| "A more detailed spec means more certainty" | Past a point, specs mislead: some things are better done than described. |
