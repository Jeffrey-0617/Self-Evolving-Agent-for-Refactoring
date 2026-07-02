#!/usr/bin/env python3
"""
Claude Agent Configuration Module

Handles all agent setup, configuration, and initialization with a flexible class-based approach.
"""

import asyncio
import os
import json
import time
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Union, Dict, List, Optional, Sequence
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultMessage,
    tool,
    create_sdk_mcp_server
)


CLAUDE_MODEL_PREFIXES = ("claude-",)
OPENAI_MODEL_PREFIXES = ("gpt-", "o", "codex-", "chatgpt-")
CODEX_LOGIN_SUCCESS_MARKERS = (
    "logged in using chatgpt",
    "logged in with chatgpt",
)


def detect_model_provider(model: Optional[str]) -> str:
    """Infer which CLI/backend should own a model name."""
    if not model:
        return "unknown"

    normalized = model.strip().lower()
    if normalized.startswith(CLAUDE_MODEL_PREFIXES):
        return "claude"
    if normalized.startswith(OPENAI_MODEL_PREFIXES):
        return "openai"
    return "unknown"


def is_openai_model(model: Optional[str]) -> bool:
    """Return True when *model* looks like an OpenAI/Codex model name."""
    return detect_model_provider(model) == "openai"


def is_claude_model(model: Optional[str]) -> bool:
    """Return True when *model* looks like a Claude model name."""
    return detect_model_provider(model) == "claude"


def _clean_codex_status_output(raw_output: str) -> str:
    lines = []
    for line in raw_output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("WARNING: proceeding, even though we could not update PATH:"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def get_codex_auth_status(cli_path: str = "codex") -> Dict[str, Any]:
    """Return parsed status information from `codex login status`."""
    completed = subprocess.run(
        [cli_path, "login", "status"],
        check=False,
        capture_output=True,
        text=True,
    )
    raw_output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part and part.strip()
    )
    summary = _clean_codex_status_output(raw_output)
    normalized_summary = summary.lower()
    logged_in = completed.returncode == 0 and any(
        marker in normalized_summary for marker in CODEX_LOGIN_SUCCESS_MARKERS
    )
    return {
        "command": f"{cli_path} login status",
        "returncode": completed.returncode,
        "logged_in": logged_in,
        "summary": summary,
        "raw_output": raw_output,
    }


def ensure_codex_oauth_login(cli_path: str = "codex") -> Dict[str, Any]:
    """Fail fast unless Codex CLI is authenticated through ChatGPT/Codex OAuth."""
    try:
        status = get_codex_auth_status(cli_path=cli_path)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Codex CLI is not installed or not on PATH. Install Codex CLI and log in with `codex login`."
        ) from exc

    if status["logged_in"]:
        return status

    observed = status["summary"] or f"exit code {status['returncode']}"
    raise RuntimeError(
        "Codex CLI is not authenticated with ChatGPT/Codex OAuth.\n"
        f"Observed status: {observed}\n"
        "Run `codex login`, complete the login flow, and rerun the batch."
    )


def build_codex_exec_command(
    *,
    model: str,
    cwd: Union[str, Path],
    cli_path: str = "codex",
    sandbox: str = "workspace-write",
    full_auto: bool = True,
    dangerously_bypass_approvals_and_sandbox: bool = False,
    reasoning_effort: Optional[str] = "medium",
    output_last_message_path: Optional[Union[str, Path]] = None,
    extra_args: Optional[Sequence[str]] = None,
) -> List[str]:
    """Build a `codex exec` command that expects the prompt on stdin."""
    command = [
        cli_path,
        "exec",
        "--cd",
        str(cwd),
        "--model",
        model,
        "--color",
        "never",
    ]
    if dangerously_bypass_approvals_and_sandbox:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        command.extend(["--sandbox", sandbox])
    if reasoning_effort:
        command.extend(["-c", f'model_reasoning_effort="{reasoning_effort}"'])
    if full_auto and not dangerously_bypass_approvals_and_sandbox:
        command.append("--full-auto")
    if output_last_message_path:
        command.extend(["--output-last-message", str(output_last_message_path)])
    if extra_args:
        command.extend(extra_args)
    command.append("-")
    return command


def format_shell_command(command: Sequence[str]) -> str:
    """Render a subprocess argument vector as a copy-pasteable shell command."""
    return " ".join(shlex.quote(part) for part in command)


class ClaudeAgent:
    """
    Flexible Claude Agent class for easy configuration and reuse.
    
    Features:
    - Dynamic configuration changes
    - Reusable across different workflows
    - Built-in usage tracking
    - Custom tool support
    """
    
    def __init__(self, config_file: str = ".env"):
        """Initialize the agent with configuration."""
        self.config_file = config_file
        self.api_key = None
        self.model = None
        self.system_prompt = None
        self.permission_mode = None
        self.working_directory = None
        self.allowed_tools = None
        self.custom_tools = {}
        self.mcp_servers = {}
        self.options = None
        self.usage_tracker = None
        
        # Load environment and initialize
        self._load_environment()
        self._setup_defaults()
    
    def _load_environment(self):
        """Load environment variables from config file."""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            print(f"✅ Loaded configuration from {self.config_file}")
        else:
            print(f"⚠️  {self.config_file} not found. Using system environment variables.")
    
    def _setup_defaults(self):
        """Setup default configuration values."""
        # Prefer the standard Anthropic env var, but allow legacy/project-specific naming.
        self.api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
        self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        self.system_prompt = os.getenv("DEFAULT_SYSTEM_PROMPT", "You are a helpful coding assistant")
        self.permission_mode = os.getenv("DEFAULT_PERMISSION_MODE", "acceptEdits")
        self.working_directory = os.getenv("DEFAULT_WORKING_DIRECTORY", os.getcwd())
        
        # Parse allowed tools (include Task for subagents)
        tools_str = os.getenv("ALLOWED_TOOLS", "Read,Write,Bash,Edit,Task")
        self.allowed_tools = [tool.strip() for tool in tools_str.split(",")]
    
    def set_model(self, model: str) -> 'ClaudeAgent':
        """Set the Claude model."""
        self.model = model
        print(f"🤖 Model set to: {model}")
        return self
    
    # def set_system_prompt(self, prompt: str) -> 'ClaudeAgent':
    #     """Set the system prompt."""
    #     self.system_prompt = prompt
    #     print(f"💭 System prompt set: {prompt[:50]}...")
    #     return self

    def set_system_prompt(self, prompt: Union[str, Dict]) -> 'ClaudeAgent':
        """Set the system prompt (string or preset dict)."""
        self.system_prompt = prompt
        if isinstance(prompt, str):
            print(f"💭 System prompt set: {prompt[:50]}...")
        else:
            print(f"💭 System prompt set: preset={prompt.get('preset')}")
        return self
    
    def set_permission_mode(self, mode: str) -> 'ClaudeAgent':
        """Set the permission mode."""
        self.permission_mode = mode
        print(f"🔒 Permission mode set to: {mode}")
        return self
    
    def set_working_directory(self, directory: str) -> 'ClaudeAgent':
        """Set the working directory."""
        self.working_directory = directory
        print(f"📁 Working directory set to: {directory}")
        return self
    
    def set_allowed_tools(self, tools: List[str]) -> 'ClaudeAgent':
        """Set the allowed tools."""
        self.allowed_tools = tools
        print(f"🔧 Allowed tools set to: {', '.join(tools)}")
        return self
    
    def add_custom_tool(self, name: str, description: str, input_schema: dict, tool_func):
        """Add a custom tool to the agent."""
        @tool(name, description, input_schema)
        async def custom_tool(args: Dict[str, Any]) -> Dict[str, Any]:
            return await tool_func(args)
        
        self.custom_tools[name] = custom_tool
        print(f"🛠️  Custom tool added: {name}")
        return self
    
    def add_system_info_tool(self) -> 'ClaudeAgent':
        """Add the built-in system info tool."""
        @tool("get_system_info", "Get basic system information", {})
        async def get_system_info(args: Dict[str, Any]) -> Dict[str, Any]:
            import platform
            
            info = {
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "working_directory": os.getcwd()
            }
            
            return {
                "content": [{
                    "type": "text",
                    "text": f"System Info: {info}"
                }]
            }
        
        self.custom_tools["get_system_info"] = get_system_info
        return self
    
    def build_options(self) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions with current configuration."""
        # Validate API key
        if not self.api_key or self.api_key == "your_claude_api_key_here":
            raise ValueError(
                "Claude API key not configured! Set ANTHROPIC_API_KEY (preferred) or CLAUDE_API_KEY."
            )
        
        # Setup MCP servers if custom tools exist
        if self.custom_tools:
            custom_server = create_sdk_mcp_server(
                name="custom_utils",
                version="1.0.0",
                tools=list(self.custom_tools.values())
            )
            self.mcp_servers = {"custom_utils": custom_server}
            
            # Add custom tool names to allowed tools
            for tool_name in self.custom_tools.keys():
                custom_tool_name = f"mcp__custom_utils__{tool_name}"
                if custom_tool_name not in self.allowed_tools:
                    self.allowed_tools.append(custom_tool_name)
        
        # Create options
        self.options = ClaudeAgentOptions(
            system_prompt=self.system_prompt,
            permission_mode=self.permission_mode,
            cwd=self.working_directory,
            allowed_tools=self.allowed_tools,
            model=self.model,
            mcp_servers=self.mcp_servers if self.mcp_servers else None,
            # Ensure the Claude Code CLI subprocess sees the API key.
            # Claude Code expects ANTHROPIC_API_KEY; this also supports repos that use CLAUDE_API_KEY.
            env={
                "ANTHROPIC_API_KEY": self.api_key,
                "CLAUDE_API_KEY": self.api_key,
            },
        )
        
        print("✅ Agent options built successfully")
        return self.options
    
    def get_options(self) -> ClaudeAgentOptions:
        """Get the current agent options."""
        if self.options is None:
            return self.build_options()
        return self.options
    
    def create_usage_tracker(self) -> 'UsageTracker':
        """Create a new usage tracker for this agent."""
        self.usage_tracker = UsageTracker()
        return self.usage_tracker
    
    def get_usage_tracker(self) -> 'UsageTracker':
        """Get the current usage tracker."""
        if self.usage_tracker is None:
            return self.create_usage_tracker()
        return self.usage_tracker
    
    def print_config(self):
        """Print current agent configuration."""
        print("\n" + "="*50)
        print("🤖 AGENT CONFIGURATION")
        print("="*50)
        print(f"Model: {self.model}")
        print(f"System Prompt: {self.system_prompt[:50]}...")
        print(f"Permission Mode: {self.permission_mode}")
        print(f"Working Directory: {self.working_directory}")
        print(f"Allowed Tools: {', '.join(self.allowed_tools)}")
        if self.custom_tools:
            print(f"Custom Tools: {', '.join(self.custom_tools.keys())}")
        print("="*50)
    
    def reset_config(self):
        """Reset configuration to defaults."""
        self._setup_defaults()
        self.options = None
        self.usage_tracker = None
        print("🔄 Configuration reset to defaults")


class UsageTracker:
    """Track actual usage from ResultMessage with detailed information."""
    
    def __init__(self):
        self.total_cost = 0.0
        self.total_turns = 0
        self.total_duration_ms = 0
        self.total_api_duration_ms = 0
        self.usage_data = []
        self.session_id = None
        self.result_messages = []
        self.context_info = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cache_read_tokens': 0,
            'total_cache_creation_tokens': 0,
            'models_used': set(),
            'external_api_tool_calls': 0,  # External tool API calls (web_search, custom MCP)
            'service_tier': None
        }
    
    def add_result(self, result: ResultMessage):
        """Add result message data to tracking with full details."""
        self.result_messages.append(result)
        
        # Basic tracking
        if result.total_cost_usd:
            self.total_cost += result.total_cost_usd
        if result.num_turns:
            self.total_turns += result.num_turns
        if result.duration_ms:
            self.total_duration_ms += result.duration_ms
        if result.duration_api_ms:
            self.total_api_duration_ms += result.duration_api_ms
        if result.session_id:
            self.session_id = result.session_id
        if result.usage:
            self.usage_data.append(result.usage)
            self._analyze_usage(result.usage)
    
    def _analyze_usage(self, usage: dict):
        """Analyze usage data for detailed context information."""
        # Token analysis
        if 'input_tokens' in usage:
            self.context_info['total_input_tokens'] += usage['input_tokens']
        if 'output_tokens' in usage:
            self.context_info['total_output_tokens'] += usage['output_tokens']
        if 'cache_read_input_tokens' in usage:
            self.context_info['total_cache_read_tokens'] += usage['cache_read_input_tokens']
        if 'cache_creation_input_tokens' in usage:
            self.context_info['total_cache_creation_tokens'] += usage['cache_creation_input_tokens']
        
        # Model information
        if 'model' in usage:
            self.context_info['models_used'].add(usage['model'])
        
        # Service tier
        if 'service_tier' in usage:
            self.context_info['service_tier'] = usage['service_tier']
        
        # External tool API calls (web_search, custom MCP tools)
        if 'server_tool_use' in usage:
            tool_use = usage['server_tool_use']
            for tool_name, count in tool_use.items():
                if isinstance(count, int):
                    self.context_info['external_api_tool_calls'] += count
    
    def print_summary(self):
        """Print comprehensive usage summary."""
        print("\n" + "="*60)
        print("📊 COMPREHENSIVE USAGE SUMMARY")
        print("="*60)
        
        # Basic metrics
        print(f"💰 Total Cost: ${self.total_cost:.4f}")
        print(f"🔄 Conversation Exchanges: {self.total_turns}")
        print(f"⏱️  Total Duration: {self.total_duration_ms}ms")
        print(f"🌐 API Duration: {self.total_api_duration_ms}ms")
        if self.session_id:
            print(f"🆔 Session ID: {self.session_id}")
        
        # Context information
        print(f"\n📊 CONTEXT ANALYSIS:")
        print(f"  📝 Your Input Tokens: {self.context_info['total_input_tokens']:,}")
        print(f"  📤 Claude's Output Tokens: {self.context_info['total_output_tokens']:,}")
        print(f"  🗄️  Cache Read Tokens: {self.context_info['total_cache_read_tokens']:,}")
        print(f"  🏗️  Cache Creation Tokens: {self.context_info['total_cache_creation_tokens']:,}")
        print(f"  🌐 External API Tool Calls: {self.context_info['external_api_tool_calls']}")
        
        # Model information
        if self.context_info['models_used']:
            print(f"  🤖 Models Used: {', '.join(self.context_info['models_used'])}")
        if self.context_info['service_tier']:
            print(f"  🏆 Service Tier: {self.context_info['service_tier']}")
        
        # Detailed usage breakdown
        if self.usage_data:
            print(f"\n📊 DETAILED USAGE BREAKDOWN:")
            for i, usage in enumerate(self.usage_data, 1):
                print(f"\n  Turn {i}:")
                for key, value in usage.items():
                    if isinstance(value, dict):
                        print(f"    {key}:")
                        for sub_key, sub_value in value.items():
                            print(f"      {sub_key}: {sub_value}")
                    else:
                        print(f"    {key}: {value}")
        
        # Cost analysis
        if self.context_info['total_input_tokens'] > 0 or self.context_info['total_output_tokens'] > 0:
            print(f"\n💰 COST ANALYSIS:")
            print(f"  Cost per input token: ${self.total_cost / max(self.context_info['total_input_tokens'], 1):.6f}")
            print(f"  Cost per output token: ${self.total_cost / max(self.context_info['total_output_tokens'], 1):.6f}")
        
        print("="*60)


def format_tool_result(content):
    """Format tool result content for readable display."""
    if isinstance(content, str):
        # Clean up the content
        lines = content.split('\n')
        
        # Filter out lines that look like command text (starting with common command patterns)
        filtered_lines = []
        skip_patterns = [
            'cat >', '<<', "EOF", "\\nEOF", 'python3 /tmp/', 
            'command:', "'}", '"}', '\\nEOF\\n'
        ]
        
        # Also detect if the content starts with command-like text
        in_command_block = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip lines that are clearly command text
            if any(line_stripped.startswith(pattern) for pattern in skip_patterns):
                continue
            
            # Detect start of command blocks (heredoc patterns)
            if '<<' in line or 'cat >' in line:
                in_command_block = True
                continue
            
            # Detect end of command blocks
            if in_command_block and ('EOF' in line or line_stripped == "'}"):
                in_command_block = False
                continue
            
            # Skip empty lines at the very start
            if not filtered_lines and not line_stripped:
                continue
            
            # Skip lines that are just command artifacts
            if line_stripped in ["'}", '"}', 'EOF', "\\nEOF"]:
                continue
            
            filtered_lines.append(line)
        
        # Join and clean up
        cleaned = '\n'.join(filtered_lines).strip()
        
        # Remove any remaining command artifacts at the start
        while cleaned.startswith("'}"):
            cleaned = cleaned[2:].strip()
        
        # Format with proper indentation
        if cleaned:
            formatted_lines = []
            for line in cleaned.split('\n'):
                # Add indentation for readability
                formatted_lines.append(f"   {line}")
            return '\n'.join(formatted_lines)
        return "   (empty result)"
    
    elif isinstance(content, list):
        # Handle list of content items
        result_parts = []
        for item in content:
            if isinstance(item, dict):
                if 'text' in item:
                    result_parts.append(item['text'])
                elif 'type' in item and item['type'] == 'text':
                    result_parts.append(item.get('text', ''))
        if result_parts:
            return format_tool_result('\n'.join(result_parts))
        return "   (no text content)"
    
    else:
        return f"   {content}"


def is_json_only(text):
    """
    Check if text contains only JSON (array or object).
    
    Args:
        text: Text to check
    
    Returns:
        True if text appears to be JSON-only, False otherwise
    """
    if not text or not text.strip():
        return False
    
    stripped = text.strip()
    
    # Check if it starts with [ or { and ends with ] or }
    if (stripped.startswith('[') and stripped.endswith(']')) or \
       (stripped.startswith('{') and stripped.endswith('}')):
        try:
            # Try to parse as JSON - if it succeeds, it's likely JSON-only
            json.loads(stripped)
            return True
        except json.JSONDecodeError:
            pass
    
    return False


# ── Terminal colours used by SubagentWatcher and print_messages ─────────────
_RESET  = "\033[0m"
_DIM    = "\033[90m"
_SUB_C  = "\033[35m"   # magenta – subagent labels
_TOOL_C = "\033[33m"   # yellow  – tool names / result headers


class SubagentWatcher:
    """
    Tails ~/.claude/projects/<hash>/*/subagents/*.jsonl in real time so that
    all intermediate subagent tool calls, results and reasoning are printed as
    they are written to disk.

    Usage::

        watcher = SubagentWatcher(project_dir=os.path.abspath(cwd))
        watcher.start()
        try:
            await print_messages(query(...), watcher=watcher)
        finally:
            watcher._poll()   # catch any final entries
            watcher.stop()
    """

    def __init__(self, project_dir: str = None):
        cwd = project_dir or os.getcwd()
        project_hash = cwd.replace("/", "-")  # leading dash intentional – do NOT strip
        self.projects_dir = Path.home() / ".claude" / "projects" / project_hash
        self.watched: dict = {}        # filepath -> lines-seen count
        self.name_map: dict = {}       # JSONL stem (agent-xxxxxxx) -> subagent type name
        self.pending_names: list = []  # subagent type names queued from Task tool calls,
                                       # assigned to new JSONL files in discovery order
        self._tool_id_map: dict = {}   # (agent_id, tool_use_id) -> tool_name
        self._start_time = time.time()
        self._task = None

    def start(self):
        self._task = asyncio.create_task(self._poll_loop())

    def stop(self):
        if self._task:
            self._task.cancel()

    async def _poll_loop(self):
        try:
            while True:
                self._poll()
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass

    def _poll(self):
        if not self.projects_dir.exists():
            return
        for jsonl in self.projects_dir.glob("*/subagents/*.jsonl"):
            if jsonl.stat().st_mtime < self._start_time:
                continue
            self._tail(jsonl)

    def _tail(self, filepath: Path):
        key = str(filepath)
        agent_id = filepath.stem
        # First time we see this file: assign a pending name if one is queued
        if key not in self.watched and agent_id not in self.name_map:
            if self.pending_names:
                self.name_map[agent_id] = self.pending_names.pop(0)
        prev = self.watched.get(key, 0)
        try:
            lines = filepath.read_text().splitlines()
        except OSError:
            return
        new_lines = lines[prev:]
        if not new_lines:
            return
        self.watched[key] = len(lines)
        for line in new_lines:
            self._print_entry(agent_id, line)

    def _print_entry(self, agent_id: str, line: str):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return
        msg = entry.get("message", {})
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Label: "SubagentType-agent-xxxxxxx" or just "agent-xxxxxxx"
        name = self.name_map.get(agent_id, "")
        label = f"{name}-{agent_id}" if name else agent_id

        if role == "assistant" and isinstance(content, list):
            for block in content:
                btype = block.get("type")
                if btype == "text" and block.get("text", "").strip():
                    print(f"{_SUB_C}[{label}]{_RESET} {block['text']}")
                elif btype == "tool_use":
                    tool_name = block.get("name", "")
                    tool_id = block.get("id", "")
                    input_data = block.get("input", {})
                    # Record id -> name so we can skip Read results below
                    if tool_id:
                        self._tool_id_map[(agent_id, tool_id)] = tool_name
                    print(f"\n{'='*60}")
                    print(f"{_SUB_C}[{label}]{_RESET} {_TOOL_C}🔧 Using tool: {tool_name}{_RESET}")
                    if isinstance(input_data, dict):
                        if "command" in input_data:
                            print(f"   Command: {input_data['command']}")
                        elif "file_path" in input_data:
                            print(f"   File: {input_data['file_path']}")
                        else:
                            print(f"   Input: {json.dumps(input_data)}")
                    print(f"{'='*60}")
                elif btype == "thinking" and block.get("thinking", "").strip():
                    print(f"{_DIM}[{label} thinking]{_RESET} {block['thinking'][:300]}")

        elif role == "user" and isinstance(content, list):
            for block in content:
                if block.get("type") == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    tool_name = self._tool_id_map.get((agent_id, tool_id), "")
                    # Skip Read tool results — the tool call already showed the file path
                    if tool_name == "Read":
                        continue
                    result = block.get("content", "")
                    if str(result).strip():
                        formatted = format_tool_result(result)
                        print(f"\n{_SUB_C}[{label}]{_RESET} {_TOOL_C}✅ Tool result:{_RESET}")
                        for result_line in formatted.split("\n"):
                            print(f"   │ {result_line}")


async def print_messages(messages, usage_tracker=None, subagent_session=None, watcher=None):
    """
    Print messages from query() in a readable format.

    Args:
        messages: AsyncIterator of messages from query()
        usage_tracker: Optional UsageTracker instance to track usage statistics
        subagent_session: Optional SubagentSession instance to track subagent sessions for resumption
        watcher: Optional SubagentWatcher instance; when provided, subagent AssistantMessages
                 are skipped here (the watcher prints them from JSONL) and watcher.name_map
                 is populated from Task tool results.
    """
    from claude_agent_sdk import TextBlock, ResultMessage, ToolUseBlock, ToolResultBlock, UserMessage, AssistantMessage

    in_subagent_section = False
    last_was_subagent = False
    task_tool_use_id = None  # Track the Task tool use ID to identify subagent messages
    tool_use_map = {}  # Map tool_use_id to tool name to skip Read tool results
    pending_task: dict = {}  # tool_use_id -> subagent_type, for watcher name_map population
    
    async for message in messages:
        # Track usage for ResultMessage
        if isinstance(message, ResultMessage) and usage_tracker:
            usage_tracker.add_result(message)
        
        # Track subagent session if provided
        if subagent_session:
            # Capture session_id
            if isinstance(message, ResultMessage) and message.session_id:
                subagent_session.session_id = message.session_id
            
            # Extract agentId from Task tool results
            if hasattr(message, 'content') and message.content:
                from claude_agent_sdk import ToolResultBlock
                for block in message.content:
                    if isinstance(block, ToolResultBlock):
                        if hasattr(block, 'content') and block.content:
                            agent_id = subagent_session.extract_agent_id(block.content)
                            if agent_id and agent_id not in subagent_session.agent_ids.values():
                                # Store with a default name or extract from context
                                agent_name = f"agent-{len(subagent_session.agent_ids)}"
                                subagent_session.agent_ids[agent_name] = agent_id
        
        # Skip printing ResultMessage - it's just metadata, the actual content is in AssistantMessage
        if isinstance(message, ResultMessage):
            continue
        
        # Handle UserMessage - skip prompts, but print tool results
        if isinstance(message, UserMessage):
            # Check if this UserMessage contains tool results (ToolResultBlock)
            if hasattr(message, 'content') and message.content:
                has_tool_result = any(
                    isinstance(block, ToolResultBlock)
                    for block in message.content
                )
                if not has_tool_result:
                    # This is a prompt/instruction, skip it
                    continue
                # If it has tool results, continue processing below
            else:
                # No content, skip it
                continue
        
        # Detect if this is a subagent message
        # According to docs: messages from subagents have parent_tool_use_id set
        is_subagent = False
        if hasattr(message, 'parent_tool_use_id') and message.parent_tool_use_id is not None:
            is_subagent = True
        elif task_tool_use_id and hasattr(message, 'content') and message.content:
            # Check if message content references the Task tool
            for block in message.content:
                if hasattr(block, 'tool_use_id') and block.tool_use_id == task_tool_use_id:
                    is_subagent = True
                    break
        
        # Also check if this is an AssistantMessage that's part of subagent context
        # (AssistantMessage with parent_tool_use_id contains subagent's text responses)
        if isinstance(message, AssistantMessage) and hasattr(message, 'parent_tool_use_id'):
            if message.parent_tool_use_id is not None:
                is_subagent = True
        
        # When a watcher is active it handles all subagent AssistantMessage output;
        # skip those here to avoid duplicates. UserMessages (tool results) still pass
        # through so we can print the "main agent received result" line.
        if watcher is not None and is_subagent and isinstance(message, AssistantMessage):
            continue

        # Close subagent section if we were in one and this is not a subagent message
        if in_subagent_section and not is_subagent:
            print(f"\n{'─'*80}")
            print("END SUBAGENT RESPONSE")
            print(f"{'─'*80}\n")
            in_subagent_section = False
        
        # Print readable formatted output
        # Check if message has content blocks
        has_content_to_print = False
        if hasattr(message, 'content') and message.content:
            # Check if there's any non-empty content to print
            for block in message.content:
                if isinstance(block, TextBlock) and block.text and block.text.strip():
                    has_content_to_print = True
                    break
                elif isinstance(block, (ToolUseBlock, ToolResultBlock)):
                    has_content_to_print = True
                    break
        
        # Open subagent section if this is a subagent message with content and we're not already in one
        if is_subagent and has_content_to_print and not in_subagent_section:
            print(f"\n{'─'*80}")
            print("🤖 SUBAGENT RESPONSE:")
            print(f"{'─'*80}")
            in_subagent_section = True
        
        # Only process content if we have something to print
        if hasattr(message, 'content') and message.content:
            # Extract and format content blocks
            for block in message.content:
                if isinstance(block, TextBlock):
                    # Skip empty text blocks (whitespace only)
                    if not block.text or not block.text.strip():
                        continue
                    
                    # Skip JSON-only responses (they'll be saved to file, no need to print)
                    if is_json_only(block.text):
                        continue
                    
                    # Indent subagent text
                    if is_subagent:
                        # Indent each line for subagent responses
                        for line in block.text.split('\n'):
                            print(f"   │ {line}")
                    else:
                        print(block.text)
                elif isinstance(block, ToolUseBlock):
                    # Track Task tool use ID to identify subagent messages
                    if block.name == 'Task' and hasattr(block, 'id'):
                        task_tool_use_id = block.id
                        # Track subagent type for watcher name_map
                        if watcher is not None:
                            st = (block.input or {}).get("subagent_type", "")
                            if st:
                                pending_task[block.id] = st
                                # Queue name so _tail can assign it the moment the
                                # JSONL file is first discovered (before any entries print)
                                watcher.pending_names.append(st)

                    # Store tool name for this tool_use_id
                    if hasattr(block, 'id'):
                        tool_use_map[block.id] = block.name
                    
                    # Show tool usage
                    tool_indicator = "🔧 [SUBAGENT] Using tool:" if is_subagent else "🔧 Using tool:"
                    print(f"\n{'='*80}")
                    print(f"{tool_indicator} {block.name}")
                    if hasattr(block, 'input') and block.input:
                        # Format input nicely
                        if isinstance(block.input, dict):
                            # Show command if it's a Bash tool
                            if 'command' in block.input:
                                cmd = block.input['command']
                                # Show first line if multi-line
                                if '\n' in cmd:
                                    first_line = cmd.split('\n')[0]
                                    print(f"   Command: {first_line}...")
                                else:
                                    print(f"   Command: {cmd}")
                            # For Read tool, show file path
                            elif 'file_path' in block.input:
                                print(f"   File: {block.input['file_path']}")
                            else:
                                print(f"   Input: {block.input}")
                        else:
                            print(f"   Input: {block.input}")
                    print(f"{'='*80}")
                elif isinstance(block, ToolResultBlock):
                    # Check if this is from a Read tool - skip printing the result
                    tool_name = None
                    if hasattr(block, 'tool_use_id'):
                        tool_name = tool_use_map.get(block.tool_use_id)
                    
                    # Skip printing Read tool results (they're too verbose)
                    if tool_name == 'Read':
                        # Just show that the read completed successfully (unless there's an error)
                        if hasattr(block, 'is_error') and block.is_error:
                            print(f"\n   ⚠️  Error reading file")
                        # Otherwise silently skip - the tool usage already showed what file was read
                        continue
                    
                    # Check if this is the Task tool result (contains subagent's final response)
                    is_task_result = (hasattr(block, 'tool_use_id') and 
                                     block.tool_use_id == task_tool_use_id)
                    
                    # If this is Task result, it contains the subagent's final response
                    # According to docs: Task tool result contains subagent output
                    if is_task_result and task_tool_use_id:
                        # Populate watcher name_map from agentId in the result
                        if watcher is not None and hasattr(block, 'tool_use_id'):
                            content_str = (
                                block.content if isinstance(block.content, str)
                                else json.dumps(block.content)
                            )
                            m = re.search(r'agentId:\s*([a-f0-9]+)', str(content_str), re.IGNORECASE)
                            if m:
                                short_id = "agent-" + m.group(1)[:7]
                                st = pending_task.pop(block.tool_use_id, "")
                                if st:
                                    watcher.name_map[short_id] = st

                        if watcher is not None:
                            # Watcher format: plain ✅ Tool result (no subagent section header)
                            print(f"\n{'='*60}")
                            print(f"[main] {_TOOL_C}✅ Tool result:{_RESET}")
                            if hasattr(block, 'content') and block.content:
                                formatted_result = format_tool_result(block.content)
                                for line in formatted_result.split('\n'):
                                    print(f"   │ {line}")
                            print(f"{'='*60}")
                        else:
                            if not in_subagent_section:
                                print(f"\n{'─'*80}")
                                print("🤖 SUBAGENT RESPONSE:")
                                print(f"{'─'*80}\n")
                                in_subagent_section = True
                            is_subagent = True

                            print(f"\n📝 SUBAGENT FINAL RESPONSE:")
                            if hasattr(block, 'content') and block.content:
                                formatted_result = format_tool_result(block.content)
                                for line in formatted_result.split('\n'):
                                    print(f"   │ {line}")
                            print()
                    else:
                        # Regular tool result (not Task)
                        result_indicator = "✅ [SUBAGENT] Tool result:" if is_subagent else "✅ Tool result:"
                        print(f"\n{result_indicator}")
                        if hasattr(block, 'content') and block.content:
                            formatted_result = format_tool_result(block.content)
                            if is_subagent:
                                # Indent subagent results
                                for line in formatted_result.split('\n'):
                                    print(f"   │ {line}")
                            else:
                                print(formatted_result)
                        else:
                            print("   (no content)")
                        if hasattr(block, 'is_error') and block.is_error:
                            print("\n   ⚠️  Error occurred")
                        print()  # Add blank line after result
        
        # Track if this was a subagent message
        last_was_subagent = is_subagent
    
    # Close subagent section if we ended while in one
    if in_subagent_section:
        print(f"\n{'─'*80}")
        print("END SUBAGENT RESPONSE")
        print(f"{'─'*80}\n")


class SubagentSession:
    """
    Helper class to track and manage subagent sessions for resumption.
    
    According to Claude SDK docs, subagents can be resumed by:
    1. Capturing session_id from ResultMessage
    2. Extracting agentId from Task tool result content
    3. Passing resume=session_id in subsequent queries
    
    Example usage:
        >>> from agent_config import SubagentSession, print_messages, create_resumable_options
        >>> from claude_agent_sdk import query, ClaudeAgentOptions
        >>> 
        >>> # First query - create subagent
        >>> session = SubagentSession()
        >>> options = ClaudeAgentOptions(allowed_tools=["Read", "Task"])
        >>> 
        >>> async for msg in query(prompt="Use Explore agent to find API endpoints", options=options):
        ...     pass  # Messages are processed by print_messages
        >>> 
        >>> # Track session during printing
        >>> await print_messages(query(prompt="...", options=options), subagent_session=session)
        >>> 
        >>> # Resume subagent in second query
        >>> if session.session_id:
        ...     resumed_options = session.get_resume_options(options)
        ...     prompt = session.get_resume_prompt(user_prompt="list the top 3 endpoints")
        ...     await print_messages(query(prompt=prompt, options=resumed_options))
    """
    
    def __init__(self):
        self.agent_ids: Dict[str, str] = {}  # agent_name -> agent_id
        self.session_id: Optional[str] = None
    
    def extract_agent_id(self, content: Any) -> Optional[str]:
        """
        Extract agentId from Task tool result content.
        
        Args:
            content: Content from ToolResultBlock (can be str, list, or dict)
        
        Returns:
            agentId string if found, None otherwise
        """
        # Convert content to string for searching
        if isinstance(content, str):
            content_str = content
        elif isinstance(content, list):
            content_str = json.dumps(content, default=str)
        elif isinstance(content, dict):
            content_str = json.dumps(content, default=str)
        else:
            content_str = str(content)
        
        # Search for agentId pattern (from docs: "agentId: <uuid>")
        match = re.search(r'agentId:\s*([a-f0-9-]+)', content_str, re.IGNORECASE)
        return match.group(1) if match else None
    
    def track_from_messages(self, messages):
        """
        Track session_id and agent_ids from message stream.
        
        Args:
            messages: AsyncIterator of messages from query()
        """
        import asyncio
        from claude_agent_sdk import ToolResultBlock
        
        async def _track():
            async for message in messages:
                # Capture session_id from ResultMessage
                if isinstance(message, ResultMessage) and message.session_id:
                    self.session_id = message.session_id
                
                # Extract agentId from Task tool results
                if hasattr(message, 'content') and message.content:
                    for block in message.content:
                        if isinstance(block, ToolResultBlock):
                            # Check if this is a Task tool result
                            if hasattr(block, 'content') and block.content:
                                agent_id = self.extract_agent_id(block.content)
                                if agent_id:
                                    # Try to identify agent name from context
                                    # For now, use a generic name or extract from prompt
                                    if 'general-purpose' not in self.agent_ids:
                                        self.agent_ids['general-purpose'] = agent_id
                                    else:
                                        # Multiple agents - use index
                                        self.agent_ids[f'agent-{len(self.agent_ids)}'] = agent_id
                yield message
        
        return _track()
    
    def get_resume_options(self, base_options: ClaudeAgentOptions) -> ClaudeAgentOptions:
        """
        Create options with resume parameter if session_id is available.
        
        Args:
            base_options: Base ClaudeAgentOptions to extend
        
        Returns:
            New ClaudeAgentOptions with resume parameter if session_id is available
        
        Example:
            >>> session = SubagentSession()
            >>> session.session_id = "abc-123"
            >>> options = ClaudeAgentOptions(allowed_tools=["Read", "Task"])
            >>> resumed = session.get_resume_options(options)
            >>> resumed.resume
            'abc-123'
        """
        return create_resumable_options(base_options, self.session_id)
    
    def get_resume_prompt(self, agent_id: Optional[str] = None, user_prompt: str = "") -> str:
        """
        Create a prompt that includes agentId for resuming a specific subagent.
        
        Args:
            agent_id: Specific agent ID to resume (if None, uses first available)
            user_prompt: User's prompt/question to append
        
        Returns:
            Formatted prompt with resume instruction
        
        Example:
            >>> session = SubagentSession()
            >>> session.agent_ids['my-agent'] = 'abc-123'
            >>> session.get_resume_prompt('abc-123', 'continue the analysis')
            'Resume agent abc-123 and continue the analysis'
        """
        target_id = agent_id
        if not target_id and self.agent_ids:
            # Use first available agent ID
            target_id = next(iter(self.agent_ids.values()))
        
        if target_id:
            return f"Resume agent {target_id} and {user_prompt}" if user_prompt else f"Resume agent {target_id}"
        return user_prompt


def extract_agent_id_from_content(content: Any) -> Optional[str]:
    """
    Extract agentId from Task tool result content.
    
    Utility function to extract agentId from various content formats.
    According to docs, agentId appears in Task tool results as "agentId: <uuid>".
    
    Args:
        content: Content from ToolResultBlock (str, list, or dict)
    
    Returns:
        agentId string if found, None otherwise
    
    Example:
        >>> content = "Some text agentId: 123e4567-e89b-12d3-a456-426614174000 more text"
        >>> extract_agent_id_from_content(content)
        '123e4567-e89b-12d3-a456-426614174000'
    """
    session = SubagentSession()
    return session.extract_agent_id(content)


def create_resumable_options(
    base_options: ClaudeAgentOptions,
    session_id: Optional[str] = None
) -> ClaudeAgentOptions:
    """
    Create ClaudeAgentOptions with resume parameter for subagent resumption.
    
    According to Claude SDK docs, you can resume a subagent by:
    1. Passing resume=session_id in query options
    2. Including the agentId in your prompt (e.g., "Resume agent <agentId> and...")
    
    Args:
        base_options: Base options to extend
        session_id: Session ID to resume (from ResultMessage.session_id)
    
    Returns:
        New ClaudeAgentOptions with resume parameter set
    
    Example:
        >>> options = ClaudeAgentOptions(allowed_tools=["Read", "Task"])
        >>> session_id = "123e4567-e89b-12d3-a456-426614174000"
        >>> resumed_options = create_resumable_options(options, session_id)
        >>> resumed_options.resume
        '123e4567-e89b-12d3-a456-426614174000'
    """
    if not session_id:
        return base_options
    
    # Create new options with resume parameter using dataclass replace
    from dataclasses import replace
    return replace(base_options, resume=session_id)


async def collect_all_messages(messages):
    """
    Collect all messages from an async iterator.
    
    Args:
        messages: AsyncIterator of messages from query()
    
    Returns:
        List of all messages collected from the iterator
    """
    all_messages = []
    async for message in messages:
        all_messages.append(message)
    return all_messages


def format_message_for_log(message):
    """
    Format a message for logging purposes.
    
    Args:
        message: A message object (UserMessage, AssistantMessage, or ResultMessage)
    
    Returns:
        Formatted string representation of the message
    """
    from claude_agent_sdk import TextBlock, ToolUseBlock, ToolResultBlock, UserMessage, AssistantMessage, ResultMessage
    
    log_lines = []
    
    if isinstance(message, UserMessage):
        log_lines.append("=" * 80)
        log_lines.append("USER MESSAGE")
        log_lines.append("=" * 80)
        if hasattr(message, 'content') and message.content:
            for block in message.content:
                if isinstance(block, TextBlock):
                    log_lines.append(f"Text: {block.text}")
                elif isinstance(block, ToolResultBlock):
                    log_lines.append(f"Tool Result (ID: {block.tool_use_id}):")
                    if hasattr(block, 'content'):
                        if isinstance(block.content, (dict, list)):
                            log_lines.append(f"  {json.dumps(block.content, indent=2)}")
                        else:
                            log_lines.append(f"  {str(block.content)}")
        log_lines.append("")
    
    elif isinstance(message, AssistantMessage):
        log_lines.append("=" * 80)
        log_lines.append("ASSISTANT MESSAGE")
        log_lines.append("=" * 80)
        if hasattr(message, 'content') and message.content:
            for block in message.content:
                if isinstance(block, TextBlock):
                    log_lines.append(f"Text: {block.text}")
                elif isinstance(block, ToolUseBlock):
                    log_lines.append(f"Tool Use (ID: {block.id}, Name: {block.name}):")
                    if hasattr(block, 'input'):
                        if isinstance(block.input, (dict, list)):
                            log_lines.append(f"  Input: {json.dumps(block.input, indent=2)}")
                        else:
                            log_lines.append(f"  Input: {str(block.input)}")
        log_lines.append("")
    
    elif isinstance(message, ResultMessage):
        log_lines.append("=" * 80)
        log_lines.append("RESULT MESSAGE (Metadata)")
        log_lines.append("=" * 80)
        log_lines.append(f"Session ID: {getattr(message, 'session_id', 'N/A')}")
        log_lines.append(f"Total Cost: ${getattr(message, 'total_cost_usd', 0):.4f}")
        log_lines.append(f"Input Tokens: {getattr(message, 'input_tokens', 0)}")
        log_lines.append(f"Output Tokens: {getattr(message, 'output_tokens', 0)}")
        log_lines.append("")
    
    return "\n".join(log_lines)


def extract_json_from_messages(messages):
    """
    Extract JSON from assistant text blocks in messages.
    
    Args:
        messages: List of message objects
    
    Returns:
        Formatted JSON string, or raw text if JSON extraction fails
    """
    from claude_agent_sdk import TextBlock, AssistantMessage
    
    json_text = ""
    
    for message in messages:
        if isinstance(message, AssistantMessage):
            if hasattr(message, 'content') and message.content:
                for block in message.content:
                    if isinstance(block, TextBlock):
                        json_text += block.text
    
    # Try to extract JSON from the text
    # Look for JSON array pattern
    json_pattern = r'\[[\s\S]*\]'
    matches = re.findall(json_pattern, json_text)
    
    if matches:
        # Take the last (likely most complete) match
        json_candidate = matches[-1]
        try:
            # Validate it's valid JSON
            parsed = json.loads(json_candidate)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            pass
    
    # If no pattern match, try to find JSON between code blocks
    code_block_pattern = r'```(?:json)?\s*(\[[\s\S]*?\])\s*```'
    matches = re.findall(code_block_pattern, json_text)
    if matches:
        json_candidate = matches[-1]
        try:
            parsed = json.loads(json_candidate)
            return json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            pass
    
    # Last resort: try to parse the entire text as JSON
    try:
        parsed = json.loads(json_text.strip())
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError:
        # Return the raw text if JSON parsing fails
        return json_text.strip()


def create_conversation_log(messages, prompt, usage_tracker=None, **context):
    """
    Create a formatted conversation log from messages.
    
    Args:
        messages: List of message objects
        prompt: Initial prompt sent to the agent
        usage_tracker: Optional UsageTracker instance
        **context: Additional context to include in the log header (e.g., legacy_library, new_library, etc.)
    
    Returns:
        Formatted log content as a string
    """
    from datetime import datetime
    
    log_lines = [
        "=" * 80,
        "CONVERSATION LOG",
        "=" * 80,
        f"Timestamp: {datetime.now().isoformat()}",
    ]
    
    # Add context information
    for key, value in context.items():
        if value:
            log_lines.append(f"{key.replace('_', ' ').title()}: {value}")
    
    log_lines.extend([
        "",
        "=" * 80,
        "INITIAL PROMPT",
        "=" * 80,
        prompt,
        "",
        "=" * 80,
        "CONVERSATION HISTORY",
        "=" * 80,
        "",
    ])
    
    # Add all messages to log
    for message in messages:
        log_lines.append(format_message_for_log(message))
    
    # Add usage summary to log
    if usage_tracker:
        log_lines.extend([
            "=" * 80,
            "USAGE SUMMARY",
            "=" * 80,
            f"Total Cost: ${usage_tracker.total_cost:.4f}",
            f"Total Turns: {usage_tracker.total_turns}",
            f"Total Input Tokens: {usage_tracker.context_info.get('total_input_tokens', 0)}",
            f"Total Output Tokens: {usage_tracker.context_info.get('total_output_tokens', 0)}",
        ])
    
    return "\n".join(log_lines)


# Convenience functions for backward compatibility
def initialize_agent() -> tuple[ClaudeAgentOptions, bool]:
    """Initialize agent with all configurations (backward compatibility)."""
    try:
        agent = ClaudeAgent()
        options = agent.build_options()
        return options, True
    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        return None, False
