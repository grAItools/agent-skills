from __future__ import annotations

import json
from pathlib import Path

from ..isolate import (
    HOST_HOME,
    NormalizedRun,
    ToolCall,
    detect_fired,
    extract_usage,
    scan_text_for_skills,
)
from .base import AgentAdapter, AgentError, install_into, merge_usage

def _events(transcript_path: Path):
    with transcript_path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event

class ClaudeCodeAdapter(AgentAdapter):
    name = "claude"

    def install_skills(self, workdir: Path, home: Path, skills: dict[str, Path]) -> list[str]:
        return install_into(workdir, ".claude/skills", skills)

    def build_command(
        self,
        prompt: str,
        model: str | None,
        max_turns: int | None,
        timeout_seconds: int | None = None,
    ) -> list[str]:
        command = [
            "claude",
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        if model:
            api_model = (
                model[len("openrouter/"):] if model.startswith("openrouter/") else model
            )
            command += ["--model", api_model]
        if max_turns:
            command += ["--max-turns", str(max_turns)]
        return command

    def runtime_env(self) -> dict[str, str]:
        import os

        if os.environ.get("EVALS_CLAUDE_OPENROUTER", "").lower() not in ("1", "true", "yes"):
            return {}
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise AgentError(
                "EVALS_CLAUDE_OPENROUTER is set but OPENROUTER_API_KEY is missing"
            )
        return {
            "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
            "ANTHROPIC_AUTH_TOKEN": key,
            "ANTHROPIC_API_KEY": key,
        }

    def credential_candidates(self) -> list[str]:
        return []

    def config_share_env(self) -> dict[str, str]:
        return {"CLAUDE_CONFIG_DIR": str(HOST_HOME / ".claude")}

    def parse(self, transcript_path: Path, raw_text: str, known: set[str]) -> NormalizedRun:
        run = NormalizedRun(parser="claude-stream-json")
        assistant_texts: list[str] = []
        for event in _events(transcript_path):
            etype = event.get("type")
            message = event.get("message") or {}
            content = message.get("content") if isinstance(message, dict) else None
            if etype == "assistant" and isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = block.get("type")
                    if block_type == "tool_use":
                        run.tool_calls.append(
                            ToolCall(name=str(block.get("name")), args=block.get("input") or {})
                        )
                    elif block_type == "text" and isinstance(block.get("text"), str):
                        assistant_texts.append(block["text"])
            elif etype == "result":
                result = event.get("result")
                if isinstance(result, str):
                    run.final_text = result
                usage = event.get("usage")
                if isinstance(usage, dict):
                    run.usage = merge_usage(run.usage, extract_usage(usage))
                cost = event.get("total_cost_usd")
                if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                    run.usage["cost_usd"] = run.usage.get("cost_usd", 0) + cost

        fired, events = detect_fired(run.tool_calls, known)
        run.fired_skills, run.skill_events = fired, events
        if not run.fired_skills:
            for skill in scan_text_for_skills(raw_text, known):
                run.fired_skills.append(skill)
                run.skill_events.append({"skill": skill, "signal": "text-scan", "tool": None})
            run.fired_skills.sort()
        if not run.final_text and assistant_texts:
            run.final_text = assistant_texts[-1]
        return run
