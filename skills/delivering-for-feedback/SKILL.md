---
name: delivering-for-feedback
description: Use when a working increment exists and release timing is in question, when stakeholders push to delay shipping for more polish or more features, or when development has run for weeks without contact with real users.
---

# Delivering for Feedback

## Overview

Creation is complete only when someone uses the thing. A release is not the end of the
cycle but the instrument that closes the loop: it converts the team's assumptions into
feedback while feedback is still cheap to act on. Late exposure of problems in the
underlying model makes them expensive — and often politically impossible — to fix.

## When to use

- Deciding when, or whether, to put a working increment in front of users.
- Pressure is mounting to "finish everything first" before anyone sees it.
- A long-running effort has had no external user contact recently.
- Planning what to observe and measure once the software is in real use.

## The process

1. **Release working software early.** Great software today usually beats perfect
   software tomorrow, and a bug-free answer to the wrong question is worthless. Early
   users contribute the corrections that make the final product right. Early means
   small in scope, never unsound: correctness, data safety, and security of what ships
   are part of "working" — cut features, not soundness.
2. **Ship increments users can actually exercise** — complete use case by complete use
   case, not "95% done" everywhere. Integrate continuously; never plan a big-bang
   integration phase.
3. **Manage expectations throughout, not at the end.** Success is measured against
   users' expectations, so keep them seeing the working increments converge. Then
   deliver a small, cheap delighter just beyond what they expected — never at the cost
   of stability.
4. **Instrument for the field:** parseable logs, a diagnostic or status view,
   self-checks. Deployed software should help diagnose itself, so that real operation
   keeps informing the design.
5. **Watch how it is really used.** Designers' use assumptions are almost always wrong
   somewhere. Observed use reveals unmet needs and unexpected uses that legitimately
   enlarge the concept — treat them as input, not annoyance.
6. **Feed everything back.** Implementation pain, performance walls, and surprising
   user behavior are requirements-and-model input for the next cycle, not
   embarrassments to patch around. Re-estimate as you learn: iterate the schedule with
   the code rather than defending an up-front plan.
7. **Know when to stop polishing.** Quality is a requirements decision negotiated with
   users, not a private ideal; don't spoil a good program with overembellishment and
   overrefinement.

## Red flags

- Weeks or months of development with no external user contact.
- "We'll demo it when it's finished."
- A big-bang integration phase anywhere in the plan.
- No way to tell, from a deployed instance, what it is doing or why it failed.
- User feedback filed as interruption rather than as input.
- Stakeholder expectations discovered for the first time at delivery.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "Users will judge us on an unpolished build" | They judge harder on a polished wrong thing. Present it honestly as a working increment. |
| "One more month will make it perfect" | Software is never perfect; iteration finds the target, polish doesn't. |
| "We already know what users need" | The besetting error of experts is confidently building the wrong thing. |
| "We'll add logging and metrics later" | Without field visibility, the loop never closes and every incident is archaeology. |
