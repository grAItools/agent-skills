from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml


class ChecksError(RuntimeError):
    pass


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


def _resolve_files(workdir: Path, spec: dict) -> list[Path]:
    if "path" in spec:
        return [workdir / str(spec["path"])]
    if "glob" in spec:
        pattern = str(spec["glob"])
        matches = sorted(p for p in workdir.glob(pattern) if p.is_file())
        if not matches and "**" in pattern:
            matches = sorted(p for p in workdir.rglob(pattern.replace("**/", "")) if p.is_file())
        return matches
    raise ChecksError("check requires 'path' or 'glob'")


def _check_file_exists(workdir: Path, spec: dict) -> CheckResult:
    files = _resolve_files(workdir, spec)
    target = spec.get("path") or spec.get("glob")
    passed = bool(files)
    detail = f"matched {len(files)} file(s)" if passed else f"no match for {target}"
    return CheckResult("file_exists", passed, detail)


def _check_file_absent(workdir: Path, spec: dict) -> CheckResult:
    files = _resolve_files(workdir, spec)
    target = spec.get("path") or spec.get("glob")
    passed = not files
    detail = "absent as required" if passed else f"found {len(files)} match(es) for {target}"
    return CheckResult("file_absent", passed, detail)


def _check_file_contains(workdir: Path, spec: dict) -> CheckResult:
    import re

    pattern = spec.get("pattern")
    if not pattern:
        raise ChecksError("file_contains requires 'pattern'")
    regex = re.compile(str(pattern), re.DOTALL)
    files = _resolve_files(workdir, spec)
    target = spec.get("path") or spec.get("glob")
    if not files:
        return CheckResult("file_contains", False, f"no files match {target}")
    for path in files:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return CheckResult("file_contains", False, f"{path}: unreadable ({exc})")
        if regex.search(content):
            return CheckResult("file_contains", True, f"pattern found in {path.relative_to(workdir)}")
    return CheckResult(
        "file_contains", False, f"pattern not found in any of {len(files)} matched file(s)"
    )


def _check_command_succeeds(workdir: Path, spec: dict, env: dict | None = None) -> CheckResult:
    command = spec.get("command")
    if not command:
        raise ChecksError("command_succeeds requires 'command'")
    timeout = int(spec.get("timeout_seconds", 120))
    argv = ["bash", "-c", str(command)]
    try:
        completed = subprocess.run(
            argv,
            cwd=workdir,
            env=env,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("command_succeeds", False, f"timed out after {timeout}s")
    tail_out = (completed.stdout or "")[-400:]
    tail_err = (completed.stderr or "")[-400:]
    passed = completed.returncode == 0
    detail = f"exit={completed.returncode}"
    if tail_err.strip():
        detail += f" stderr…: {tail_err.strip()[-200:]}"
    if not passed and tail_out.strip():
        detail += f" stdout…: {tail_out.strip()[-200:]}"
    return CheckResult("command_succeeds", passed, detail)


_CHECKS = {
    "file_exists": _check_file_exists,
    "file_absent": _check_file_absent,
    "file_contains": _check_file_contains,
}

_KNOWN_CHECKS = sorted(_CHECKS) + ["command_succeeds"]

_SAFE_ARG_KEYS = {"path", "glob", "pattern", "command", "timeout_seconds"}


def run_checks(checks_path: Path, workdir: Path, env: dict | None = None) -> list[CheckResult]:
    raw = yaml.safe_load(checks_path.read_text(encoding="utf-8")) or {}
    entries = raw.get("checks")
    if not isinstance(entries, list) or not entries:
        raise ChecksError(f"{checks_path.name}: must contain a non-empty 'checks:' list")
    results: list[CheckResult] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ChecksError(f"{checks_path.name}: check #{index} is not a mapping")
        check_type = entry.get("type")
        if check_type == "command_succeeds":
            result = _check_command_succeeds(workdir, entry, env)
        else:
            handler = _CHECKS.get(check_type)
            if handler is None:
                raise ChecksError(
                    f"{checks_path.name}: unknown check type '{check_type}' "
                    f"(known: {_KNOWN_CHECKS})"
                )
            result = handler(workdir, entry)
        unexpected = set(entry) - _SAFE_ARG_KEYS - {"type"}
        if unexpected:
            raise ChecksError(f"{checks_path.name}: unexpected keys {sorted(unexpected)}")
        results.append(result)
    return results
