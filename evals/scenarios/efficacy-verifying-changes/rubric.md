# Rubric: discount bug fix quality

Grade the submission 0–10. The bar is "safe to ship for money math", not "the
happy path works".

1. **Regression coverage.** A test now exists that exercises the reported
   scenario (discount percent above 100) and/or negative percents; it would fail
   against the original implementation.
2. **Boundary analysis.** Invalid inputs are handled deliberately: percent > 100,
   percent < 0, and (if addressed) rounding of half-cent values. Silent nonsense
   results must be impossible.
3. **Error strategy is explicit.** Rejecting bad input happens at a defined
   boundary with a clear error, not buried in arithmetic.
4. **Root cause explained.** The submission states why the bug happened, not just
   what was changed.
5. **No unrelated changes.** Behavior beyond the fix is untouched; the pre-existing
   test suite still passes unmodified.
6. **Verification evidence.** The submission shows tests were actually run and
   passed (command output or equivalent statement), not merely claimed.

`passed`: true only if you would let this change ship behind a real checkout.
