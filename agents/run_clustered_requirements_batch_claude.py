#!/usr/bin/env python3
"""
Claude-Code-CLI-backed clustered requirements batch runner.

This keeps the same behavior as run_clustered_requirements_batch.py, but swaps
the backend to refactoring_agent_claude_cli.py. Authentication is forced through
ANTHROPIC_API_KEY loaded from the environment or .env.
"""

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from agents import run_clustered_requirements_batch as batch  # noqa: E402
from agents.refactoring_agent_claude_cli import run_refactoring_task  # noqa: E402

batch.run_refactoring_task = run_refactoring_task
batch.DEFAULT_AGENT = PROJECT_DIR / "agents" / "refactoring_agent_claude_cli.py"
batch.DEFAULT_PROVIDER = "claude-cli-api"


if __name__ == "__main__":
    batch.main()
