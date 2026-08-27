from __future__ import annotations

from pathlib import Path

from ..isolate import HOST_HOME
from .base import AgentAdapter, install_into


class OpenCodeAdapter(AgentAdapter):
    name = "opencode"

    def install_skills(self, workdir: Path, home: Path, skills: dict[str, Path]) -> list[str]:
        return install_into(workdir, ".claude/skills", skills)

    def build_command(
        self,
        prompt: str,
        model: str | None,
        max_turns: int | None,
        timeout_seconds: int | None = None,
    ) -> list[str]:
        command = ["opencode", "run", "--format", "json"]
        if model:
            command += ["--model", model]
        command += ["--auto", prompt]
        return command

    def credential_candidates(self) -> list[str]:
        return [".local/share/opencode/auth.json"]

    def config_share_env(self) -> dict[str, str]:
        return {"XDG_DATA_HOME": str(HOST_HOME / ".local" / "share")}
