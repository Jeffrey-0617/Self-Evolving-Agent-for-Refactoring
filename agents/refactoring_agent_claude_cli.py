#!/usr/bin/env python3
"""
API-key-backed Claude Code CLI entry point for Wright# refactoring.

This backend shells out to `claude -p` so the run uses the Claude Code CLI
agent loop directly, while forcing API-key billing through ANTHROPIC_API_KEY
loaded from the environment or .env.
"""

import argparse
import asyncio
import codecs
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from agents.refactoring_agent_subscription import (  # noqa: E402
    MAIN_AGENT_PROMPT,
    MonitoringTee,
    TMP_DIR,
    build_prompt,
    compute_final_verification_outcome,
    load_adl_input,
    load_assertions,
)


API_KEY_ENV_VARS = ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY")


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE lines without requiring python-dotenv."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_api_key() -> str:
    load_env_file(Path(PROJECT_DIR) / ".env")
    for name in API_KEY_ENV_VARS:
        value = os.environ.get(name)
        if value and value != "your_claude_api_key_here":
            return value
    raise RuntimeError(
        "Claude API key not configured. Set ANTHROPIC_API_KEY, or CLAUDE_API_KEY, "
        "in your environment or in .env."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wright# ADL refactoring agent using Claude Code CLI API-key auth",
    )
    parser.add_argument(
        "--adl",
        required=True,
        help="System name (e.g. eshop), path to .adl file, or raw ADL text",
    )
    parser.add_argument(
        "--requirement",
        required=True,
        help="Refactoring requirement in natural language",
    )
    parser.add_argument(
        "--language-type",
        required=True,
        help="ADL language type (e.g. wrighthash)",
    )
    parser.add_argument(
        "--assertions",
        required=False,
        default=None,
        help="Optional extra assertion statements to append after generated ones (file path or raw text)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Claude Code model to use. Default: claude-sonnet-4-6",
    )
    return parser.parse_args()


def build_cli_command(model: str, prompt: str) -> list[str]:
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--permission-mode",
        "acceptEdits",
        "--setting-sources",
        "user,project",
        "--allowedTools",
        "Read,Write,Bash,Edit,Task,Skill",
        "--disallowedTools",
        "Bash(git *)",
        "Bash(gh *)",
        "Read(./.git/**)",
        "--append-system-prompt",
        MAIN_AGENT_PROMPT,
        "--output-format",
        "stream-json",
        "--verbose",
        "--no-session-persistence",
        prompt,
    ]


def build_cli_env(api_key: str) -> dict[str, str]:
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = api_key
    env["CLAUDE_API_KEY"] = api_key
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    env.setdefault("CLAUDE_CODE_MAX_OUTPUT_TOKENS", "128000")
    return env



def _text_from_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
                elif item.get("text"):
                    parts.append(str(item["text"]))
            elif item is not None:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _print_block(text: str) -> None:
    for line in text.splitlines():
        print(line)


def _emit_message_content(message: dict[str, Any], state: dict[str, Any]) -> None:
    role = message.get("role", "assistant")
    content = message.get("content", [])
    if isinstance(content, str):
        _print_block(content)
        return
    if not isinstance(content, list):
        return

    actor = "main"
    for part in content:
        if not isinstance(part, dict):
            if part is not None:
                print(str(part))
            continue

        part_type = part.get("type")
        if part_type == "text":
            _print_block(str(part.get("text", "")))
            continue

        if part_type == "tool_use":
            tool_name = str(part.get("name", "unknown"))
            tool_input = part.get("input") or {}
            print(f"[{actor}] Using tool: {tool_name}")
            print("Input:", json.dumps(tool_input, ensure_ascii=True))
            if tool_name == "Bash" and isinstance(tool_input, dict):
                command = tool_input.get("command")
                if command:
                    print(f"Command: {command}")
            continue

        if part_type == "tool_result":
            tool_text = _text_from_content(part.get("content"))
            if tool_text:
                _print_block(tool_text)
            continue

        if role == "assistant" and part.get("text"):
            _print_block(str(part["text"]))


def _emit_cli_event(line: str, state: dict[str, Any]) -> None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        print(line)
        return

    event_type = event.get("type")
    if event_type == "system" and event.get("subtype") == "init":
        session_id = event.get("session_id")
        if session_id:
            state["session_id"] = session_id
            print(f"Claude Code session: {session_id}")
        return

    if event_type in {"assistant", "user"}:
        message = event.get("message")
        if isinstance(message, dict):
            _emit_message_content(message, state)
        return

    if event_type == "result":
        state["result_event"] = event
        if event.get("total_cost_usd") is not None:
            state["total_cost_usd"] = float(event["total_cost_usd"])
        if event.get("duration_ms") is not None:
            state["total_duration_ms"] = int(event["duration_ms"])
        result_text = event.get("result")
        if result_text:
            print(result_text)
        if event.get("subtype") and event.get("subtype") != "success":
            print("Claude Code result subtype:", event.get("subtype"))
        return

    if event.get("message"):
        print(str(event["message"]))


async def run_claude_cli(command: list[str], env: dict[str, str]) -> dict[str, Any]:
    state: dict[str, Any] = {
        "total_cost_usd": 0.0,
        "total_duration_ms": 0,
        "session_id": "",
        "result_event": None,
    }
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=os.path.abspath(PROJECT_DIR),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )



    # assert process.stdout is not None
    # while True:
    #     raw_line = await process.stdout.readline()
    #     if not raw_line:
    #         break
    #     line = raw_line.decode("utf-8", errors="replace").rstrip("\n")
    #     if line:
    #         _emit_cli_event(line, state)
    assert process.stdout is not None

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    pending = ""

    while True:
        chunk = await process.stdout.read(65536)
        if not chunk:
            break

        pending += decoder.decode(chunk)

        while "\n" in pending:
            line, pending = pending.split("\n", 1)
            line = line.rstrip("\r")
            if line:
                _emit_cli_event(line, state)

    # Flush any final output if Gemini CLI exits without a trailing newline.
    pending += decoder.decode(b"", final=True)
    pending = pending.strip()
    if pending:
        _emit_cli_event(pending, state)


    return_code = await process.wait()
    state["return_code"] = return_code
    if return_code != 0:
        raise RuntimeError(f"Claude Code CLI failed with exit code {return_code}")
    return state


async def run_refactoring_task(
    *,
    adl: str,
    requirement: str,
    language_type: str,
    assertions: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> dict:
    adl_text = load_adl_input(adl)
    extra_assertions = load_assertions(assertions) if assertions else None

    os.makedirs(TMP_DIR, exist_ok=True)
    log_path = os.path.join(TMP_DIR, "log.md")
    log_file = open(log_path, "w", encoding="utf-8")

    original_stdout = sys.stdout
    tee = MonitoringTee(original_stdout, log_file)
    sys.stdout = tee
    final_verification_outcome = "not_recorded"
    cli_state: dict[str, Any] = {"total_cost_usd": 0.0, "total_duration_ms": 0}

    try:
        print(f"\n{'=' * 60}")
        print("  REFACTORING AGENT (CLAUDE CODE CLI API KEY)")
        print(f"{'=' * 60}")
        print(f"  ADL source      : {adl}")
        print(f"  Requirement     : {requirement}")
        print(f"  Language type   : {language_type}")
        print(f"  Model           : {model}")
        if extra_assertions:
            print(f"  Extra assertions: {len(extra_assertions.splitlines())} line(s) provided")
        print(f"{'=' * 60}\n")

        api_key = get_api_key()
        print("Auth mode          : Claude Code CLI with ANTHROPIC_API_KEY")

        prompt = build_prompt(language_type, requirement, adl_text, extra_assertions)
        command = build_cli_command(model, prompt)
        print("Starting refactoring agent through Claude Code CLI ...\n")
        cli_state = await run_claude_cli(command, build_cli_env(api_key))

        final_verification_outcome = compute_final_verification_outcome()
        if final_verification_outcome == "valid":
            print("Full property verification: **valid**")
        elif final_verification_outcome == "invalid":
            print("Full property verification: **invalid**")
        else:
            print("Full property verification: **not_recorded**")
        print(f"Total Cost: ${float(cli_state.get('total_cost_usd', 0.0)):.4f}")
        print(f"Total Duration: {int(cli_state.get('total_duration_ms', 0))}ms")
    finally:
        sys.stdout = original_stdout
        if not log_file.closed:
            log_file.close()
        print(
            f"\n[Run stats] refactored.adl updates: {tee.refactored_adl_updates}, "
            f"verification runs: {tee.verification_runs}"
        )

    return {
        "log_path": log_path,
        "verification_outcome": final_verification_outcome,
        "verification_runs": tee.verification_runs,
        "verification_loop_count": tee.verification_runs,
        "verification_records": tee.verification_attempts,
        "refactored_updates": tee.refactored_adl_updates,
        "total_cost_usd": float(cli_state.get("total_cost_usd", 0.0)),
        "total_duration_ms": int(cli_state.get("total_duration_ms", 0)),
    }


async def run() -> None:
    args = parse_args()
    await run_refactoring_task(
        adl=args.adl,
        requirement=args.requirement,
        language_type=args.language_type,
        assertions=args.assertions,
        model=args.model,
    )


def main() -> None:
    try:
        asyncio.run(run())
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
