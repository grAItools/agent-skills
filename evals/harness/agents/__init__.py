from __future__ import annotations

from .base import AgentAdapter, AgentError
from .claude import ClaudeCodeAdapter
from .opencode import OpenCodeAdapter
from .pilike import PiLikeAdapter

__all__ = [
    "AgentAdapter",
    "AgentError",
    "ClaudeCodeAdapter",
    "OpenCodeAdapter",
    "PiLikeAdapter",
    "build_adapters",
]


def build_adapters() -> dict[str, AgentAdapter]:
    adapters: list[AgentAdapter] = [
        ClaudeCodeAdapter(),
        OpenCodeAdapter(),
        PiLikeAdapter("pi", "pi"),
        PiLikeAdapter("omp", "omp", config_dir=".omp/agent"),
    ]
    return {adapter.name: adapter for adapter in adapters}
