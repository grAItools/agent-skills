from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

HOST_HOME = Path.home()

UNSET_ENV_KEYS = [
    "CLAUDE_CONFIG_DIR",
    "PI_CODING_AGENT_DIR",
    "PI_CODING_AGENT_SESSION_DIR",
    "OPENCODE_CONFIG",
    "OPENCODE_CONFIG_DIR",
    "OPENCODE_CONFIG_CONTENT",
]

XDG_DIRS = {
    "XDG_CONFIG_HOME": ".config",
    "XDG_CACHE_HOME": ".cache",
    "XDG_DATA_HOME": ".local/share",
    "XDG_STATE_HOME": ".local/state",
}


@dataclass
class IsolatedEnv:
    env: dict[str, str]
    home: Path
    workdir: Path
    seeded: list[str] = field(default_factory=list)


def build_cell_env(cell_dir: Path, workdir: Path) -> IsolatedEnv:
    home = cell_dir / "home"
    tmp = cell_dir / "tmp"
    home.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    for key in UNSET_ENV_KEYS:
        env.pop(key, None)
    env["HOME"] = str(home)
    for key, rel in XDG_DIRS.items():
        target = home / rel
        target.mkdir(parents=True, exist_ok=True)
        env[key] = str(target)
    env["TMPDIR"] = str(tmp)
    env["NO_COLOR"] = "1"
    env["EVALS_CELL_DIR"] = str(cell_dir)
    return IsolatedEnv(env=env, home=home, workdir=workdir)


def seed_credentials(iso: IsolatedEnv, relative_paths: list[str]) -> list[str]:
    copied = []
    for rel in relative_paths:
        src = HOST_HOME / rel
        if not src.is_file():
            continue
        dst = iso.home / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied


_SKILL_PATH_RE = re.compile(r"[A-Za-z0-9_-]+/SKILL\.md")


def resolve_skill_ref(ref: str, known: set[str]) -> str | None:
    ref = ref.strip().strip("'\"")
    if ":" in ref:
        ref = ref.rsplit(":", 1)[1]
    return ref if ref in known else None


@dataclass
class ToolCall:
    name: str
    args: dict

    def blob(self, limit: int = 1200) -> str:
        try:
            payload = json.dumps(self.args, default=str)
        except Exception:
            payload = str(self.args)
        return f"{self.name} {payload[:limit]}"

    def to_dict(self) -> dict:
        preview = self.blob()
        return {"name": self.name, "args_preview": preview[len(self.name) + 1:]}


@dataclass
class NormalizedRun:
    exit_code: int = 0
    timed_out: bool = False
    duration_seconds: float = 0.0
    fired_skills: list[str] = field(default_factory=list)
    skill_events: list[dict] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    final_text: str = ""
    parser: str = "none"

    def to_dict(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "duration_seconds": round(self.duration_seconds, 2),
            "fired_skills": self.fired_skills,
            "skill_events": self.skill_events,
            "tool_calls": [t.to_dict() for t in self.tool_calls[:200]],
            "usage": self.usage,
            "final_text": self.final_text[:4000],
            "parser": self.parser,
        }


_USAGE_ALIASES = {
    "input_tokens": ["input_tokens", "inputTokens", "prompt_tokens", "promptTokens"],
    "output_tokens": ["output_tokens", "outputTokens", "completion_tokens", "completionTokens"],
    "cache_read_tokens": [
        "cache_read_input_tokens",
        "cacheReadInputTokens",
        "cache_read_tokens",
        "cached_tokens",
        "cachedTokens",
    ],
    "cache_write_tokens": [
        "cache_creation_input_tokens",
        "cacheCreationInputTokens",
        "cache_write_tokens",
    ],
    "cost_usd": ["total_cost_usd", "totalCostUsd", "cost_usd", "costUSD", "cost"],
}


def extract_usage(obj: object) -> dict:
    sums: dict[str, float] = {}

    def add(bucket: str, value: float) -> None:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            sums[bucket] = sums.get(bucket, 0) + value

    def walk(node: object) -> None:
        if isinstance(node, dict):
            tokens = node.get("tokens")
            if isinstance(tokens, dict):
                add("input_tokens", tokens.get("input"))
                add("output_tokens", tokens.get("output"))
                add("reasoning_tokens", tokens.get("reasoning"))
                cache = tokens.get("cache") or {}
                if isinstance(cache, dict):
                    add("cache_read_tokens", cache.get("read"))
                    add("cache_write_tokens", cache.get("write"))
            usage = node.get("usage")
            if isinstance(usage, dict) and ("totalTokens" in usage or isinstance(usage.get("cost"), dict)):
                add("input_tokens", usage.get("input"))
                add("output_tokens", usage.get("output"))
                add("reasoning_tokens", usage.get("reasoningTokens"))
                add("cache_read_tokens", usage.get("cacheRead"))
                add("cache_write_tokens", usage.get("cacheWrite"))
                cost = usage.get("cost") or {}
                if isinstance(cost, dict):
                    add("cost_usd", cost.get("total"))
            for key, value in node.items():
                for bucket, aliases in _USAGE_ALIASES.items():
                    if key in aliases and isinstance(value, (int, float)) and not isinstance(value, bool):
                        sums[bucket] = sums.get(bucket, 0) + value
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    for key in list(sums):
        if key.endswith("_tokens"):
            sums[key] = int(sums[key])
    return sums


def iter_dicts(node: object):
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            yield current
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


_TOOL_USE_TYPES = {"tool_use", "tool_call", "tool", "toolCall"}
_TEXT_TYPES = {"text", "message"}


def _extract_tool_args(node: dict) -> tuple[str | None, object]:
    if node.get("type") in _TOOL_USE_TYPES:
        state = node.get("state")
        name = node.get("name") or node.get("tool") or node.get("toolName")
        args = (
            node.get("input")
            or node.get("args")
            or node.get("arguments")
            or (state.get("input") if isinstance(state, dict) else None)
            or {}
        )
        return (name if isinstance(name, str) else None), args
    return None, None


def detect_fired(tool_calls: list[ToolCall], known: set[str]) -> tuple[list[str], list[dict]]:
    fired: set[str] = set()
    events: list[dict] = []
    for call in tool_calls:
        name_lower = call.name.lower()
        hits: set[str] = set()

        if name_lower == "skill":
            for value in call.args.values():
                if isinstance(value, str):
                    resolved = resolve_skill_ref(value, known)
                    if resolved:
                        hits.add(resolved)

        if not hits and "skill" in name_lower:
            blob = call.blob()
            for skill in known:
                if re.search(rf"(?:^|[^A-Za-z0-9_-]){re.escape(skill)}(?:[^A-Za-z0-9_-]|$)", blob):
                    hits.add(skill)

        if not hits:
            blob = call.blob()
            for match in _SKILL_PATH_RE.findall(blob):
                candidate = match.split("/")[0]
                if candidate in known:
                    hits.add(candidate)

        signal = "skill-tool" if name_lower == "skill" else ("skill-loader" if "skill" in name_lower else "path-read")
        for hit in sorted(hits):
            if hit not in fired:
                fired.add(hit)
                events.append({"skill": hit, "signal": signal, "tool": call.name})
    return sorted(fired), events


def scan_text_for_skills(raw_text: str, known: set[str]) -> list[str]:
    fired = set()
    for match in _SKILL_PATH_RE.findall(raw_text):
        candidate = match.split("/")[0]
        if candidate in known:
            fired.add(candidate)
    return sorted(fired)
