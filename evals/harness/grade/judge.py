from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field

API_URL = "https://api.anthropic.com/v1/messages"
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
API_VERSION = "2023-06-01"
DEFAULT_JUDGE_MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 4096
FILE_CHAR_LIMIT = 8000
MAX_FILES = 12
DIFF_CHAR_LIMIT = 30000
FINAL_CHAR_LIMIT = 6000


class JudgeError(RuntimeError):
    pass


@dataclass
class JudgeVerdict:
    passed: bool
    score: float
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    notes: str = ""
    model: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "score": self.score,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "notes": self.notes,
            "model": self.model,
        }


SYSTEM_PROMPT = """You are a strict, skeptical grader of coding-agent work. You grade one \
submission at a time against an explicit rubric. You did not see how the work was produced \
and you must not speculate about tools or agents involved. Grade only what is in front of \
you. Be conservative: when a rubric criterion is only partially met, score it partially or \
not at all. Respond with a single JSON object and nothing else."""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [truncated {len(text) - limit} chars]"


def _render_submission(submission: dict) -> str:
    parts: list[str] = []
    final_message = submission.get("final_message") or "(no final message)"
    parts.append("## Agent's final message\n" + _truncate(str(final_message), FINAL_CHAR_LIMIT))
    changed = submission.get("changed_files") or []
    if changed:
        parts.append(f"## Files created or modified ({len(changed)} shown)")
        for entry in changed[:MAX_FILES]:
            body = _truncate(str(entry.get("content", "")), FILE_CHAR_LIMIT)
            parts.append(f"### {entry.get('path')}\n```\n{body}\n```")
    diff = submission.get("diff")
    if diff:
        parts.append("## Diff against the starting fixture\n```diff\n"
                     + _truncate(str(diff), DIFF_CHAR_LIMIT)
                     + "\n```")
    return "\n\n".join(parts)


def _build_user_prompt(task: str, rubric: str, submission: dict) -> str:
    return (
        "# Task given to the worker\n\n"
        f"{task.strip()}\n\n"
        "# Grading rubric\n\n"
        f"{rubric.strip()}\n\n"
        "# Submission to grade\n\n"
        f"{_render_submission(submission)}\n\n"
        "# Your job\n\n"
        "Score the submission against every rubric criterion from 0 to 10 overall "
        "(10 = all criteria fully met). Then respond with ONLY this JSON object:\n"
        '{"passed": <true|false>, "score": <0-10>, '
        '"strengths": [<short strings>], "weaknesses": [<short strings>], '
        '"notes": "<one paragraph justification>"}\n'
        "`passed` is true only when the submission would satisfy the intent behind the "
        "rubric, not merely its letter."
    )


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise JudgeError(f"no JSON object in judge response: {text[:300]}")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise JudgeError(f"judge response is not valid JSON ({exc}): {text[:300]}") from exc
    if not isinstance(parsed, dict):
        raise JudgeError("judge response JSON is not an object")
    return parsed


def _request_json(url: str, payload: dict, headers: dict, timeout: int = 180) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise JudgeError(f"judge API returned HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise JudgeError(f"judge API call failed: {exc}") from exc


def _judge_via_openrouter(
    task: str,
    rubric: str,
    submission: dict,
    model: str | None,
    api_key: str | None,
) -> tuple[str, str]:
    model = model or os.environ.get("EVALS_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("EVALS_JUDGE_API_KEY")
    if not api_key:
        raise JudgeError(
            "no API key for OpenRouter judge: export OPENROUTER_API_KEY (or EVALS_JUDGE_API_KEY)"
        )
    payload = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(task, rubric, submission)},
        ],
    }
    body = _request_json(
        OPENROUTER_API_URL,
        payload,
        {
            "content-type": "application/json",
            "authorization": f"Bearer {api_key}",
            "x-title": "graitools-evals",
        },
    )
    choices = body.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise JudgeError(f"openrouter judge response has no choices: {str(body)[:300]}")
    message = choices[0].get("message") or {}
    text = str(message.get("content") or "").strip()
    if not text:
        raise JudgeError("openrouter judge returned empty content")
    return text, model


def judge_submission(
    task: str,
    rubric: str,
    submission: dict,
    model: str | None = None,
    api_key: str | None = None,
) -> JudgeVerdict:
    provider = os.environ.get("EVALS_JUDGE_PROVIDER", "anthropic").strip().lower()

    if provider == "openrouter":
        text, used_model = _judge_via_openrouter(task, rubric, submission, model, api_key)
    else:
        model = model or os.environ.get("EVALS_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise JudgeError(
                "no API key for judge: set ANTHROPIC_API_KEY or EVALS_JUDGE_API_KEY"
            )
        payload = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "temperature": 0,
            "system": SYSTEM_PROMPT,
            "messages": [
                {"role": "user", "content": _build_user_prompt(task, rubric, submission)}
            ],
        }
        body = _request_json(
            API_URL,
            payload,
            {
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": API_VERSION,
            },
        )
        blocks = body.get("content") or []
        text = "".join(
            block.get("text", "") for block in blocks if isinstance(block, dict)
        ).strip()
        if not text:
            raise JudgeError("judge API returned no text content")
        used_model = model

    parsed = _extract_json(text)

    score = parsed.get("score")
    passed = parsed.get("passed")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise JudgeError(f"judge returned non-numeric score: {score!r}")
    if not isinstance(passed, bool):
        passed = float(score) >= 7.0
    return JudgeVerdict(
        passed=bool(passed),
        score=float(score),
        strengths=[str(s) for s in parsed.get("strengths", [])][:8],
        weaknesses=[str(w) for w in parsed.get("weaknesses", [])][:8],
        notes=str(parsed.get("notes", ""))[:2000],
        model=used_model,
    )
