"""Drive the Vibe copilot through a local AI coding-agent CLI instead of an API.

When the backend runs on the user's own machine, it can shell out to a locally
installed and logged-in `claude` (Claude Code) or `codex` (OpenAI Codex) CLI in
headless mode. Both authenticate with the user's existing subscription, so the
copilot needs NO API key.

Each function takes the already-built Vibecut prompt and the JSON Schema of the
expected structured response, runs the CLI, and returns the parsed dict for the
caller to validate against FunctionCallResponse.
"""

import asyncio
import copy
import json
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_VALID_BACKENDS = ("gemini", "claude_code", "codex")


def detect_backend(requested: str | None, gemini_available: bool) -> str:
    """Resolve which copilot engine to use, favouring zero-friction defaults.

    An explicit AI_BACKEND wins. Otherwise ("auto" or unset) we prefer a locally
    installed agent CLI — no API key needed — and only fall back to Gemini.
    """
    choice = (requested or "auto").strip().lower()
    if choice in _VALID_BACKENDS:
        return choice
    if shutil.which("claude"):
        return "claude_code"
    if shutil.which("codex"):
        return "codex"
    return "gemini"

_CLI_TIMEOUT_SECONDS = 180

_SYSTEM_PROMPT = (
    "You are Vibecut, an AI video-editing assistant. Decide the single tool call "
    "that satisfies the user's request, or return assistant_message with "
    "function_call=null for greetings or ambiguous requests. Respond with the "
    "structured output only — no prose, no code fences."
)


class CliBackendError(RuntimeError):
    """Raised when the agent CLI is missing, times out, or returns bad output."""


def _strictify_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a JSON Schema satisfy OpenAI strict structured-output rules.

    Every object must set additionalProperties=false and list all of its
    properties as required. Mutates a copy so the caller's schema is untouched.
    Harmless for Claude Code, required for Codex.
    """
    clone = copy.deepcopy(schema)

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and isinstance(node.get("properties"), dict):
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(clone)
    return clone


async def _run(cmd: list[str], *, stdin: bytes | None = None) -> tuple[int, bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(input=stdin), timeout=_CLI_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        proc.kill()
        raise CliBackendError("The AI agent CLI timed out.") from exc
    return proc.returncode or 0, out, err


async def call_claude_code(prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Run Claude Code headlessly and return the structured response dict."""
    cmd = [
        "claude",
        "-p",
        prompt,
        "--append-system-prompt",
        _SYSTEM_PROMPT,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema),
    ]
    code, out, err = await _run(cmd)
    if code != 0:
        logger.warning("claude CLI exited %s: %s", code, err.decode(errors="replace")[:500])
        raise CliBackendError("Claude Code CLI failed. Is it installed and logged in?")
    try:
        envelope = json.loads(out)
    except json.JSONDecodeError as exc:
        raise CliBackendError("Could not parse Claude Code output.") from exc
    structured = envelope.get("structured_output")
    if not isinstance(structured, dict):
        raise CliBackendError("Claude Code returned no structured output.")
    return structured


async def call_codex(prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
    """Run Codex headlessly and return the structured response dict."""
    strict_schema = _strictify_schema(schema)
    with tempfile.TemporaryDirectory(prefix="vibecut_codex_") as tmpdir:
        schema_path = Path(tmpdir) / "schema.json"
        out_path = Path(tmpdir) / "out.json"
        schema_path.write_text(json.dumps(strict_schema))
        cmd = [
            "codex",
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--output-schema",
            str(schema_path),
            "-o",
            str(out_path),
            f"{_SYSTEM_PROMPT}\n\n{prompt}",
        ]
        code, out, err = await _run(cmd)
        if code != 0:
            logger.warning("codex CLI exited %s: %s", code, err.decode(errors="replace")[:500])
            raise CliBackendError("Codex CLI failed. Is it installed and logged in?")
        try:
            structured: dict[str, Any] = json.loads(out_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise CliBackendError("Could not parse Codex output.") from exc
    return structured
