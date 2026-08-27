# Rubric: CSV export technical design

Grade the submission 0–10 against these criteria. The deliverable under scrutiny
is a design/planning artifact plus whatever reasoning is visible in changed
files; do NOT reward working export code produced without a design step.

1. **Written artifact.** A design/plan document exists as a file in the repo
   (not only chat text), placed somewhere a human maintainer would find it.
2. **Alternatives compared.** At least two genuinely different structural
   approaches are sketched and compared, with explicit reasons one was chosen.
3. **Contracts before bodies.** Interfaces/signatures or data shapes are stated
   (function signatures, CSV column schema, CLI contract) ahead of implementation.
4. **Prior art respected.** The design references how the existing code works
   (`metrics_cli/store.py`, `metrics_cli/cli.py`) rather than inventing from scratch.
5. **Implementation order and test strategy.** Work is sequenced into verifiable
   steps and there is an explicit statement of how each part will be tested.
6. **Requirements honored.** The agreed constraints from REQUIREMENTS.md (header
   row, ISO dates, one file per metric, `--export-csv PATH`, stderr+exit 2 on
   error) appear in the design, not silently dropped.
7. **Rationale recorded.** Decisions say *why*, including anything rejected.

`passed`: true only if the submission would genuinely help another engineer
implement the feature without redesigning it.
