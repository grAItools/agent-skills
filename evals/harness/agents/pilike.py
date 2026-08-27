from __future__ import annotations

from pathlib import Path

from .base import AgentAdapter, install_into


class PiLikeAdapter(AgentAdapter):
    def __init__(self, name: str, binary: str, config_dir: str = ".pi/agent") -> None:
        self.name = name
        self.binary = binary
        self.config_dir = config_dir

    def install_skills(self, workdir: Path, home: Path, skills: dict[str, Path]) -> list[str]:
        return install_into(home / self.config_dir, "skills", skills)

    def build_command(
        self,
        prompt: str,
        model: str | None,
        max_turns: int | None,
        timeout_seconds: int | None = None,
    ) -> list[str]:
        command = [self.binary, "-p", "--mode", "json", "--no-session"]
        if model:
            command += ["--model", model]
        if timeout_seconds and self.name == "omp":
            command += ["--max-time", str(timeout_seconds)]
        if self.name == "omp":
            command += ["--auto-approve"]
        command.append(prompt)
        return command

    def credential_candidates(self) -> list[str]:
        candidates = [
            f"{self.config_dir}/auth.json",
            ".local/share/pi/agent/auth.json",
        ]
        if self.name == "omp":
            candidates.append(f"{self.config_dir}/config.yml")
        return candidates

    def config_share_env(self) -> dict[str, str]:
        if self.name == "pi":
            import os

            return {"PI_CODING_AGENT_DIR": os.path.expanduser("~/.pi/agent")}
        return {}
