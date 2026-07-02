#!/usr/bin/env python3
"""
Usage:
    python agents/refactoring_agent_subscription.py \
        --adl eshop \
        --requirement "Add a loyalty rewards system for customers" \
        --language-type wrighthash \
        --assertions "..."   # optional

This is the single subscription-backed entry point for refactoring.
It uses Claude Code's subscription/OAuth login flow instead of Console
API-key billing. It intentionally avoids loading `.env` and strips
higher-precedence API auth variables for the Claude Code session.
"""

import argparse
import asyncio
import io
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager, redirect_stdout
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_DIR)

from agents.agent_config import (
    SubagentSession,
    SubagentWatcher,
    UsageTracker,
    print_messages,
)
from agents.verification.verify_wrighthash_all_properties import verify_from_files
from claude_agent_sdk import ClaudeAgentOptions, query


TMP_DIR = os.path.join(PROJECT_DIR, "tmp")
SUBSCRIPTION_ONLY_AUTH_VARS = (
    "ANTHROPIC_API_KEY",
    "CLAUDE_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
)


class MonitoringTee:
    """Write to both an underlying stream and a file; count refactored.adl updates and verification runs."""

    REFACTORED_PATTERN = "refactored.adl"
    REFACTORED_WRITE_MARKERS = ("> tmp/refactored.adl", ">> tmp/refactored.adl")
    VERIFY_COMMAND_REGEXES = (
        re.compile(r"^\s*Command:\s*python3?\s+agents/verification/verify_wrighthash_all_properties\.py\b"),
        re.compile(r"^\s*Command:\s*python3?\s+-m\s+agents\.verification\.verify_wrighthash_all_properties\b"),
    )

    def __init__(self, stream, file_handle):
        self._stream = stream
        self._file = file_handle
        self.refactored_adl_updates = 0
        self.verification_attempts = []
        self._buffer = ""
        self._pending_verification_index = None
        self._last_context_line = ""

    @property
    def verification_runs(self) -> int:
        return len(self.verification_attempts)

    def _start_verification_attempt(self, reason: str | None = None) -> None:
        self.verification_attempts.append(
            {
                "attempt_number": len(self.verification_attempts) + 1,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "finished_at": None,
                "exit_code": None,
                "reason": reason or "verification check",
            }
        )
        self._pending_verification_index = len(self.verification_attempts) - 1

    def _finish_verification_attempt(self, exit_code: int | None = None) -> None:
        if self._pending_verification_index is None:
            return
        attempt = self.verification_attempts[self._pending_verification_index]
        if attempt["finished_at"] is None:
            attempt["finished_at"] = datetime.now().isoformat(timespec="seconds")
        if exit_code is not None:
            attempt["exit_code"] = exit_code
        self._pending_verification_index = None

    def _infer_reason(self) -> str:
        context = self._last_context_line.strip()
        if not context:
            return "verification check"
        lowered = context.lower()
        if "step 4" in lowered or "verify" in lowered:
            return "post-refactor check"
        if "fix" in lowered:
            return context
        return context

    def _check_line(self, line: str) -> None:
        stripped = line.strip()
        if self.REFACTORED_PATTERN in line:
            if any(marker in line for marker in self.REFACTORED_WRITE_MARKERS):
                self.refactored_adl_updates += 1
            elif " > " in line or " >> " in line:
                self.refactored_adl_updates += 1
        if any(regex.search(line) for regex in self.VERIFY_COMMAND_REGEXES):
            self._finish_verification_attempt()
            self._start_verification_attempt(self._infer_reason())
        elif self._pending_verification_index is not None:
            if stripped in {"valid", "invalid"} or stripped.startswith("✅ Tool result:") or stripped.startswith("⚠️"):
                self._finish_verification_attempt()
            else:
                match = re.search(r"\bExit code:\s*(-?\d+)\b", stripped)
                if match:
                    self._finish_verification_attempt(int(match.group(1)))
        if stripped and not stripped.startswith("Command:"):
            self._last_context_line = stripped

    def write(self, data):
        self._stream.write(data)
        self._stream.flush()
        if self._file and not self._file.closed:
            self._file.write(data)
            self._file.flush()
        self._buffer += data
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._check_line(line)

    def flush(self):
        if self._buffer:
            self._check_line(self._buffer)
            self._buffer = ""
        self._finish_verification_attempt()
        self._stream.flush()
        if self._file and not self._file.closed:
            self._file.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


MAIN_AGENT_PROMPT = """
You are a main agent for Refactoring Wright# ADL designs.

Here is the Refactoring workflow:

Use the Skill tool to invoke **refactoring-workflow** and **strictly** follow all steps in that skill, and **never** skip any step. There are 7 STEPS in refactoring-workflow, make sure you complete all of them.

"""


def load_adl_input(adl_arg: str) -> str:
    """Resolve *adl_arg* to ADL text (file path -> system name -> raw text)."""
    if os.path.isfile(adl_arg):
        with open(adl_arg, encoding="utf-8") as handle:
            return handle.read()

    candidate = os.path.join(PROJECT_DIR, "wrighthashADL", f"{adl_arg}.adl")
    if os.path.isfile(candidate):
        with open(candidate, encoding="utf-8") as handle:
            return handle.read()

    return adl_arg


def load_assertions(assertions_arg: str) -> str:
    """Resolve *assertions_arg* to assertion text (file path or raw text)."""
    if os.path.isfile(assertions_arg):
        with open(assertions_arg, encoding="utf-8") as handle:
            return handle.read().strip()
    return assertions_arg.strip()


def parse_args():
    parser = argparse.ArgumentParser(
        description="Wright# ADL refactoring agent using Claude Code subscription auth",
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


def get_claude_auth_status() -> dict:
    """Return parsed `claude auth status` output."""
    completed = subprocess.run(
        ["claude", "auth", "status", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (completed.stdout or completed.stderr or "").strip()

    if completed.returncode != 0 and not output:
        raise RuntimeError("Failed to read Claude Code authentication status.")

    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse Claude Code authentication status: {output}") from exc


def is_claude_ai_subscription_login(status: dict) -> bool:
    """Return True when Claude Code reports a Claude.ai login-backed session."""
    return bool(status.get("loggedIn")) and status.get("authMethod") == "claude.ai"


def describe_auth_mode(status: dict) -> str:
    """Describe the effective auth mode based on Claude Code status."""
    if is_claude_ai_subscription_login(status):
        return "Claude.ai subscription login via Claude Code CLI"
    if status.get("loggedIn"):
        return (
            "Logged in, but not via Claude.ai subscription "
            f"(authMethod={status.get('authMethod')}, apiProvider={status.get('apiProvider')})"
        )
    return "Not logged in for Claude.ai subscription"


def ensure_subscription_login() -> dict:
    """Fail fast unless Claude Code is logged in via subscription/OAuth."""
    try:
        status = get_claude_auth_status()
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Claude Code CLI is not installed. Install it with: npm install -g @anthropic-ai/claude-code"
        ) from exc

    if is_claude_ai_subscription_login(status):
        return status

    raise RuntimeError(
        "Claude Code is not authenticated with a Claude.ai subscription login.\n"
        f"Observed status: loggedIn={status.get('loggedIn')} "
        f"authMethod={status.get('authMethod')} apiProvider={status.get('apiProvider')}\n"
        "Run `claude auth login` in your terminal, complete the browser login, then rerun this agent.\n"
        "This subscription-backed agent intentionally does not fall back to ANTHROPIC_API_KEY or CLAUDE_API_KEY."
    )


@contextmanager
def subscription_auth_environment():
    """Temporarily remove higher-precedence API auth vars so Claude Code uses subscription OAuth."""
    removed = {}
    for key in SUBSCRIPTION_ONLY_AUTH_VARS:
        if key in os.environ:
            removed[key] = os.environ.pop(key)
    try:
        yield removed
    finally:
        os.environ.update(removed)


def build_options(model: str) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        cwd=os.path.abspath(PROJECT_DIR),
        allowed_tools=["Read", "Write", "Bash", "Edit", "Task", "Skill"],
        disallowed_tools=[
            "Bash(git *)",
            "Bash(gh *)",
            "Read(./.git/**)",
        ],
        model=model,
        permission_mode="acceptEdits",
        setting_sources=["user", "project"],
        system_prompt={
            "type": "preset",
            "preset": "claude_code",
            "append": f"\n\n{MAIN_AGENT_PROMPT}",
        },
    )


def build_prompt(language_type: str, requirement: str, adl_text: str, extra_assertions: str | None) -> str:
    prompt = f"""\
## Refactoring Task

**Language type:** {language_type}
**Requirement:** {requirement}

**Current ADL design:**
```
{adl_text}
```

Follow the workflow described in your system prompt.

Important run constraints:
- Verification is capped at 4 total attempts, including the first verification. After the 4th attempt, stop fixing and finish the workflow with the current result.
"""

    wrighthash_syntax_rules = """
Wrighthash Syntax Rules:
Rule 1: Port names must be unique (within each component and across all components) and differ from their own event names
Rule 2: Each input role of a connector instance can only be attached to one component port
Rule 3: One component port can only be attached to at most one input role
Rule 4: Every declared connector instance must have all its roles attached (no incomplete attachments)
Rule 5: Role names in attach statements must match connector definitions exactly
Rule 6 (Attach ordering): In a <*> multi-role attachment, at most one input role is allowed, and it must appear before all output roles.

Connector Semantics:
- Defines reusable interaction patterns between components
- Data exchange occurs through channels that connect roles:
    - Output channels (ch!j): Send data from one role to another
    - Input channels (ch?j): Receive data from another role
- Output Role: Initiates interaction with parameter j, sends data j via output channels
- Input Role: Receives data via input channels
- Each role represents a participant in the communication using CSP-style processes
- The "process" event in a role's sequence determines when the attached component port executes, the "process" event is necessary!

2.1.3 Example of a clinet server connector (CSConnector):
connector CSConnector {
    role requester(j) = process -> req!j -> res?j -> Skip;
    role responder() = req?j -> invoke -> process -> res!j -> responder();
}
- requester is the output role, and responder is the input role.
- requester hits process first -> requester's attached component port executes
- requester sends req!j
- responder receives req?j, triggers invoke
- responder hits process -> responder's attached component port executes
- responder sends res!j, requester receives res?j
"""

    if extra_assertions:
        prompt += f"""\
## User-provided assertions

{extra_assertions}

"""

    return prompt + wrighthash_syntax_rules


def compute_final_verification_outcome() -> str:
    """Use the existing verification function directly on the final tmp files."""
    adl_path = os.path.join(PROJECT_DIR, "tmp", "refactored.adl")
    assertions_path = os.path.join(PROJECT_DIR, "tmp", "assertions.md")
    if not (os.path.isfile(adl_path) and os.path.isfile(assertions_path)):
        return "not_recorded"

    try:
        with redirect_stdout(io.StringIO()):
            return verify_from_files(adl_path=adl_path, assertions_path=assertions_path)
    except Exception:
        return "not_recorded"


def print_structured_run_summary(tracker: UsageTracker, verification_outcome: str) -> None:
    """Emit parse-friendly summary lines using the existing usage tracker fields."""
    if verification_outcome == "valid":
        print("Full property verification: **valid** ✓")
    elif verification_outcome == "invalid":
        print("Full property verification: **invalid** ✗")
    else:
        print("Full property verification: **not_recorded**")
    print(f"Total Cost: ${tracker.total_cost:.4f}")
    print(f"Total Duration: {tracker.total_duration_ms}ms")


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

    try:
        print(f"\n{'=' * 60}")
        print("  REFACTORING AGENT (CLAUDE CODE SUBSCRIPTION)")
        print(f"{'=' * 60}")
        print(f"  ADL source      : {adl}")
        print(f"  Requirement     : {requirement}")
        print(f"  Language type   : {language_type}")
        print(f"  Model           : {model}")
        if extra_assertions:
            print(f"  Extra assertions: {len(extra_assertions.splitlines())} line(s) provided")
        print(f"{'=' * 60}\n")

        auth_status = ensure_subscription_login()
        print(
            "Claude Code auth   : "
            f"loggedIn={auth_status.get('loggedIn')} "
            f"authMethod={auth_status.get('authMethod')} "
            f"apiProvider={auth_status.get('apiProvider')}"
        )
        print(f"Auth mode          : {describe_auth_mode(auth_status)}")

        tracker = UsageTracker()
        session = SubagentSession()
        watcher = SubagentWatcher(project_dir=os.path.abspath(PROJECT_DIR))
        options = build_options(model)
        prompt = build_prompt(language_type, requirement, adl_text, extra_assertions)

        print("Starting refactoring agent with subscription-backed Claude Code ...\n")
        watcher.start()
        try:
            with subscription_auth_environment() as removed_auth:
                if removed_auth:
                    print(
                        "API key override   : ignoring higher-precedence auth vars for this run: "
                        + ", ".join(sorted(removed_auth))
                    )
                await print_messages(
                    query(prompt=prompt, options=options),
                    usage_tracker=tracker,
                    subagent_session=session,
                    watcher=watcher,
                )
        finally:
            watcher._poll()
            watcher.stop()

        final_verification_outcome = compute_final_verification_outcome()
        tracker.print_summary()
        print_structured_run_summary(tracker, final_verification_outcome)
    finally:
        sys.stdout = original_stdout
        if not log_file.closed:
            log_file.close()
        print(f"\n[Run stats] refactored.adl updates: {tee.refactored_adl_updates}, verification runs: {tee.verification_runs}")

    return {
        "log_path": log_path,
        "verification_outcome": final_verification_outcome,
        "verification_runs": tee.verification_runs,
        "verification_loop_count": tee.verification_runs,
        "verification_records": tee.verification_attempts,
        "refactored_updates": tee.refactored_adl_updates,
        "total_cost_usd": tracker.total_cost,
        "total_duration_ms": tracker.total_duration_ms,
    }


async def run():
    args = parse_args()
    await run_refactoring_task(
        adl=args.adl,
        requirement=args.requirement,
        language_type=args.language_type,
        assertions=args.assertions,
        model=args.model,
    )


def main():
    try:
        asyncio.run(run())
    except RuntimeError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
