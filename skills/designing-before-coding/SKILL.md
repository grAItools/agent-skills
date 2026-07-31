---
name: designing-before-coding
description: Use when deciding how to build something — choosing module boundaries, interfaces, data models, or system structure — after the need is understood and before writing production code, when a change calls for a new abstraction rather than a bolt-on, or when evaluating an existing architecture.
---

# Designing Before Coding

## Overview

Complexity is the single enemy of software design: anything about a system's structure that makes it hard to understand and modify. It is caused by dependencies and obscurity, it is felt by readers rather than writers, and it accumulates incrementally — so it must be fought in every decision, however small. The unit of development is an **abstraction, not a feature**: when a feature needs a new abstraction, design it cleanly and somewhat general-purpose all at once, rather than bolting the feature on. Design is iterative discovery, not plan execution — goals, constraints, and the best structure are found *while* designing, the first idea is rarely the best, and design time is repaid many times over in implementation and rework saved.

The output of this skill is a design/plan document good enough that someone else could implement it — with the reasoning preserved.

## When to Use

- An agreed set of requirements needs a technical design or implementation plan.
- Choosing module boundaries, interfaces, data models, layering, or inter-service relationships.
- An existing structure must change to accommodate a feature.
- A "how should we build this?" question, or an architecture review.

Do not use when requirements are still unclear (establish those first) or for trivial changes that fit the existing design cleanly — but decide that consciously, don't assume it.

## Before Designing

**Interrogate the framing.** The besetting mistake of experienced designers is not designing the thing wrong but designing the *wrong thing*. Ask: what is this system really? Is it secretly a language, a database, a workflow engine? Are the assumptions it rests on still valid, or has the ground shifted? Mis-stating the problem leads to wrong thinking throughout; a pedestrian vision cannot be fixed by excellent detailing.

**Study prior art.** Examine how the existing codebase, and comparable systems elsewhere, solve similar problems — including their failures and the reasons behind them. Originality is no excuse for ignorance: innovate only where you expect real improvement, and adopt proven solutions everywhere else. When studying a precedent, assume competence: ask "what led a smart designer to do this?" and reconstruct the constraints that made it sensible.

**List the constraints and name the scarce resource.** Constraints are friends — they narrow the search space and sharpen the design. Write them all down, mark which are real, obsolete, misperceived, or self-imposed, and identify the one budgeted resource the design must ration (latency, memory, bandwidth, schedule, concept count, ...). Track its projected spending visibly throughout the design; verify the assumed bottleneck with an early measurement, and be ready to discover mid-design that the true scarce resource is a different one.

**Make the user model explicit.** Who calls this, how often, knowing what, wanting what? Write it down with weightings; guess concretely where facts run out. Wrong explicit assumptions get corrected; vague ones don't.

## Design It Twice

For every significant decision — decomposition, interface, data model — sketch **at least two genuinely different designs** before committing. Rough out each one's key interfaces, then compare:

- Ease of use for callers and higher layers (the most important criterion).
- Interface simplicity and generality.
- Performance headroom and implementation cost.
- How each would absorb the changes you can foresee.

Even when the first idea wins, the comparison teaches you *why* — and when all alternatives look bad, their shared problems point to a better third design. Skipping this step because the first idea "seems obviously right" is how hard problems defeat smart people. Scale the effort to the decision's blast radius — an hour or two for a class, more for a system boundary; the comparison is the point, not polish. Record the losing alternatives and the reasons; the rationale is part of the design.

## Module Design Rules

- **Make modules deep.** A module's benefit is its functionality; its cost to the system is its interface. Aim for simple interfaces hiding substantial implementations. An interface barely simpler than its implementation adds cost without benefit.
- **Write interface contracts before bodies.** Class and operation descriptions, preconditions, postconditions, invariants — written before any implementation exists. If a simple, complete description is hard to write, the design is wrong; fix the design, not the wording.
- **Hide information.** Each module should encapsulate design decisions — formats, algorithms, assumptions — that appear nowhere in its interface, so the decision can change without touching other modules. Never return or accept internal data structures across an interface.
- **Decompose by knowledge, not by execution order.** Structure that mirrors "first read, then parse, then write" spreads the same knowledge across several places. Group code by what it *knows*, and the order of operations takes care of itself.
- **Make interfaces somewhat general-purpose.** The implementation serves today's need; the interface should serve a class of needs. A public method designed for exactly one call site is a warning. But don't over-generalize: if callers need lots of wrapper code, the interface is too low-level.
- **Separate general from special.** Special-purpose (application, UI, policy) code lives in higher layers; general mechanisms live below, with no knowledge of their specific uses.
- **Different layer, different abstraction.** Adjacent layers exposing near-identical interfaces (pass-through methods, thin wrappers) signal a wrong division of responsibility: merge, redistribute, or let callers go direct.
- **Pull complexity downward.** When something is unavoidably hard, solve it inside the module rather than exporting it via exceptions or configuration parameters — a module has more users than implementers. Treat every configuration parameter as a design failure to justify: could the module compute the value better than its users can?
- **Eliminate effects between unrelated things.** A change in one requirement should touch one module. Design components that are self-contained with a single well-defined purpose; avoid shared mutable state and hidden ordering dependencies. Design as if components will run concurrently — it forces cleaner interfaces even if you never deploy that way.
- **Represent knowledge once.** Every fact should have one authoritative home — in code, schema, configuration, and documentation alike. Where two forms must exist, generate one from the other.
- **Keep decisions reversible.** Abstract third-party products, deployment models, and volatile technology choices behind interfaces you own; put changeable details (business policy, tunable choices) in configuration or data rather than in code. There are no final decisions — order the work so the decisions least likely to change are made first, and the rest stay soft beneath them.

## Designing the Error Story

Error handling is a disproportionate source of complexity and production failures, so design it deliberately:

1. **Define errors out of existence** where possible: redefine operations so the "error" case is normal, well-defined behavior (deleting a missing entry is a no-op; a range query over an out-of-bounds span returns the overlap).
2. **Mask** low-level conditions inside the module that can handle them (retry, recover) so callers never see them.
3. **Aggregate** what remains: let rare exceptional conditions propagate to one handler at the top of the request loop instead of scattering handlers at every call site.
4. **Crash cleanly** on truly unhandleable states (corruption, impossible invariants) — a dead process does less damage than a crippled one — but never swallow errors that callers need for correctness.

## Modeling the Domain

- Keep a **dedicated domain layer**, free of UI, application-coordination, and infrastructure concerns; keep the application layer thin — orchestration only, no business rules.
- Name every element with the exact terms the domain experts use; when the language changes in conversation, the model — and the code — change with it.
- Classify domain objects deliberately: **entities** (a thread of identity over time), **values** (immutable descriptive wholes, equal by attributes; put complex logic here, with operations that return new values), and stateless **services** for operations that belong to no object. Don't drain entities into data bags with all logic in services.
- Draw explicit **consistency boundaries**: cluster entities/values under one root, enforce invariants within the boundary at each commit, reference other clusters only by their roots, and let cross-boundary consistency be asynchronous.
- **Make implicit concepts explicit.** When experts use a word with no counterpart in the code, or a business rule hides inside a conditional, reify it as a named class, method, or rule object.
- In a large system, don't force one unified model. Name each model's **bounded context**, map how the contexts actually relate, and choose every relationship consciously — share a kernel, consume upstream as a customer, conform to it, translate through an isolation layer, or stay apart. When integrating with a legacy or external model, translate at the boundary in your own terms rather than absorbing its representation. First ask whether integration is needed at all: it is always expensive.
- Identify the small **core** that differentiates the system; spend the best design effort there and justify everything else by how it supports the core. Build the first end-to-end slice through the core, not through an easy peripheral.

## De-risking the Design

- **Prototype to learn.** For anything risky, unproven, or uncomfortable — an algorithm, a third-party dependency, a performance question — build a small throwaway spike that answers the specific question. Its value is the lesson, not the code; label it disposable and never ship it.
- **Build a tracer skeleton.** For a new system, get a thin end-to-end slice working early: every architectural component present and connected, each doing a trivial version of its job. Unlike a prototype, this skeleton is written to production standard and kept — it becomes the frame everything else fills in, an always-working integration platform, and proof the architecture holds together. Keep every intermediate state complete and consistent.
- **Walk the scenarios.** Run every known usage scenario through the proposed design on paper before coding — including low-frequency ones; they surface requirements and flaws nothing else will. Re-walk them after each design change. A scenario that won't flow cleanly is a design defect found at the cheapest possible time.
- **Design for testability.** If you cannot describe how a module will be tested in isolation, it is too coupled. Testability pressure is a cheap, honest probe of decoupling.

## Conceptual Integrity and Rationale

- A coherent design reflects one set of consistent decisions. Give the design a single owner (or a tightly aligned pair) with real authority over it; negotiation among many peers produces bloated committee designs where nobody says no. Collaborate hard on exploration and on review — but let the design itself flow from one mind. (Working solo, this is automatic — the rule forbids design-by-committee; it doesn't require a committee.)
- Consistency is the deepest form of quality: given partial knowledge of the system, a reader should be able to predict the rest. Apply three tests to every addition: does it link things that are independent (breaks orthogonality)? does it introduce anything immaterial to the need (breaks propriety)? does it restrict something inherently general (breaks generality — when you don't know how it will be used, grant freedom)?
- Beware imposed simplicity below the task's inherent complexity — the complexity will break out elsewhere as jury-rigged workarounds. Match the design's expressive power to the real problem.
- **Record the whys.** For every major decision, write down what was chosen, what was rejected, and why. Maintainers who don't know why a stone is load-bearing will remove it.

## The Plan

Produce a design/plan document (store it wherever the project keeps such documents) containing:

1. **Context** — the need being served, in one paragraph; link or restate the agreed requirements.
2. **Constraints and budgeted resource** — audited list; the scarce resource and its allocation.
3. **The design** — modules and responsibilities, interfaces (signatures plus behavioral contracts), data model, error strategy.
4. **Alternatives considered** — at least one genuinely different design and why it lost.
5. **Risks and spikes** — open technical questions and the prototypes that will answer them, done *before* the plan is declared ready.
6. **Implementation order** — steps sized for independent verification, starting with a tracer skeleton through the core; least-reversible decisions earliest.
7. **Test strategy** — how each part will be verified against its contract.

Mark the plan READY only when the risky assumptions have been tested and the scenarios walk cleanly through the design. Scale the document to the decision's blast radius — a design note can be enough for a class; a system boundary deserves the full structure.

## Red Flags

| Symptom | What it means |
|---|---|
| Interface barely simpler than its implementation | Shallow module; cost without benefit |
| Same design decision reflected in several modules | Information leakage; restructure around the knowledge |
| Structure mirrors runtime order of operations | Temporal decomposition; regroup by knowledge |
| Common operations force awareness of rare features | Overexposure; split or default the rare parts |
| Method that only forwards to a similar method | Responsibility boundary in the wrong place |
| General mechanism containing code for one specific use | Special–general mixture; push the specifics up |
| Configuration parameter punting a decision the module could make | Complexity exported upward; pull it down |
| Committing to the first sketch without a rival | Design-it-twice skipped; you don't know why this design wins |
| One model silently spanning two teams or subsystems | Unmapped context boundary; expect false cognates |
| Entities as data bags, logic all in services | Anemic model; behavior belongs with the data |
| Business rule visible only as a buried conditional | Implicit concept; name it and promote it |
| Recurring "unexpected" changes hitting the same spot | The model is wrong there; deepen it instead of patching |
| Requirements only expressible awkwardly in the model | Listen to the awkwardness; a concept is missing |
| Design proceeding on unspoken user assumptions | Vague user model; write it down, even wrong |
| A constraint nobody has re-validated | Possibly obsolete; sometimes removing it is the breakthrough |

## Common Rationalizations

| Excuse | Reality |
|---|---|
| "No time to design twice" | A second sketch costs an hour or two against weeks of implementation. |
| "We'll generalize it later" | The implementation can stay specific; the interface is what must not be. |
| "It's a small feature, no design needed" | Complexity is incremental; small bolt-ons are exactly how systems rot. |
| "The requirements force this design" | Requirements state needed properties, never implementations. Push back on how-constraints. |
