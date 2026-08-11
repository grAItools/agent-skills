#!/usr/bin/env bash
#
# Validate every skill in this repository.
#
# Two tools do the work, both pinned, neither maintained here:
#
#   skills-ref   the reference validator for the open format — frontmatter
#                syntax, the fields it defines, the limits it sets
#   skillscheck  the published specification and its own house rules — broken
#                links, leaked secrets, oversized assets, plugin manifests
#
# skillscheck runs under --strict, so a warning fails the run too; skills-ref has
# no such mode and reports errors only. Pinning is what makes --strict safe: a
# version that gains checks cannot start failing pull requests that changed
# nothing. Bump the pins deliberately, and read what the new version says before
# you do.
#
# CI runs this file rather than its own copy of these commands, so a green tick
# locally and a green tick on a pull request mean the same thing.
#
# Usage:  scripts/check.sh
# Exit:   0 clean, 1 if either tool objects.

set -euo pipefail

SKILLS_REF_VERSION=0.1.1
SKILLSCHECK_VERSION=0.9.5

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v uvx >/dev/null 2>&1; then
    echo "error: uvx is required to run the validators." >&2
    echo "       install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

status=0

# Invoked as a module rather than by name so this does not depend on a
# console-script shim landing on PATH.
echo "==> skills-ref ${SKILLS_REF_VERSION}: the open format"
for dir in skills/*/; do
    uvx --quiet --from "skills-ref==${SKILLS_REF_VERSION}" \
        python -m skills_ref.cli validate "$dir" || status=1
done

echo
echo "==> skillscheck ${SKILLSCHECK_VERSION}: the specification, warnings included"
uvx --quiet "skillscheck@${SKILLSCHECK_VERSION}" . --strict || status=1

echo
if [ "$status" -ne 0 ]; then
    echo "Validation failed. See CONTRIBUTING.md for what the contract asks of a skill."
else
    echo "All skills valid."
fi
exit "$status"
