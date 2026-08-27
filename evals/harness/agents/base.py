from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from ..isolate import (
    _TEXT_TYPES,
    NormalizedRun,
    ToolCall,
    _extract_tool_args,
    detect_fired,
    extract_usage,
    iter_dicts,
    scan_text_for_skills,
)


class AgentError(RuntimeError):
    pass


class AgentAdapter(ABC):
    name: str = "abstract"

    @abstractmethod
    def install_skills(self, workdir: Path, home: Path, skills: dict[str, Path]) -> list[str]:
        ...

    @abstractmethod
    def build_command(
        self,
        prompt: str,
        model: str | None,
        max_turns: int | None,
        timeout_seconds: int | None = None,
    ) -> list[str]:
        ...

    def credential_candidates(self) -> list[str]:
        return []

    def config_share_env(self) -> dict[str, str]:
        return {}

    def runtime_env(self) -> dict[str, str]:
        return {}

    def parse(self, transcript_path: Path, raw_text: str, known: set[str]) -> NormalizedRun:
        return parse_stream_tolerant(transcript_path, raw_text, known)


_AUTH_FAILURE_MARKERS = (
    "failed to authenticate",
    "oauth session expired",
    "could not be refreshed",
    "api key", "unauthorized",
)


def looks_like_auth_failure(text: str) -> bool:
    head = text.strip().lower()[:400]
    return any(marker in head for marker in _AUTH_FAILURE_MARKERS)


def _link_skill(skills_target: Path, source: Path) -> None:
    skills_target.mkdir(parents=True, exist_ok=True)
    destination = skills_target / source.name
    if destination.exists():
        raise AgentError(f"skill already installed at {destination}")
    destination.symlink_to(source.resolve(), target_is_directory=True)


def install_into(base_dir: Path, rel: str, skills: dict[str, Path]) -> list[str]:
    target = base_dir / rel
    for source in sorted(skills.values()):
        _link_skill(target, source)
    return [str(target)]


def merge_usage(base: dict, delta: dict) -> dict:
    merged = dict(base)
    for key, value in delta.items():
        merged[key] = merged.get(key, 0) + value
    return merged


def parse_stream_tolerant(transcript_path: Path, raw_text: str, known: set[str]) -> NormalizedRun:
    run = NormalizedRun(parser="tolerant")
    texts: list[str] = []
    latest_usage: dict = {}
    latest_total = -1

    def _snapshot(u: dict) -> int:
        return int(u.get("input_tokens", 0)) + int(u.get("output_tokens", 0))

    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                texts.append(line[:2000])
                continue
            if not isinstance(event, (dict, list)):
                continue
            for node in iter_dicts(event):
                tool_name, args = _extract_tool_args(node)
                if isinstance(tool_name, str) and isinstance(args, dict):
                    run.tool_calls.append(ToolCall(name=tool_name, args=args))
                text = node.get("text")
                if isinstance(text, str) and node.get("type") in _TEXT_TYPES:
                    texts.append(text)
                for key in ("result", "response"):
                    value = node.get(key)
                    if isinstance(value, str) and len(value) > len(run.final_text):
                        run.final_text = value

            snapshot = extract_usage(event)
            if _snapshot(snapshot) > latest_total:
                latest_total = _snapshot(snapshot)
                latest_usage = snapshot
    run.usage = latest_usage

    fired, events = detect_fired(run.tool_calls, known)
    run.fired_skills, run.skill_events = fired, events
    if not run.fired_skills:
        for skill in scan_text_for_skills(raw_text, known):
            run.fired_skills.append(skill)
            run.skill_events.append({"skill": skill, "signal": "text-scan", "tool": None})
        run.fired_skills.sort()
    if texts and len(texts[-1]) > len(run.final_text):
        run.final_text = texts[-1]
    return run
