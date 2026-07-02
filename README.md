# Self-Evolving Agent for Software Architecture Refactoring

This repository implements a self-evolving LLM agent that refactors software architecture designs based on natural-language functional requirements. The agent is **self-evolving**: it starts with a fixed set of cold-start skills and no memory, and accumulates reusable knowledge across tasks.

---

## Agent Knowledge

### Cold-start Skills
The agent ships with a set of pre-defined skills in `.claude/skills/`. These are available from the very first task:

| Skill | Purpose |
|---|---|
| `refactoring-workflow` | Defines the Essential workflow of the agents: generate assertions, refacor designs, verify, repair |
| `retrieval` | Retrieve relevant memory before starting a task |
| `post-reflection` | After a task, distill the run log into reusable memory entries and update skills |
| `wrighthash-tool-apply` | Apply static analysis tools|
| `wrighthash-tool-gen` | Create or update static analysis tools |
| `distill` | Record a mistake pattern mid-task |

### Evolving Memory
The agent starts with **no memory**. Across tasks, it writes two types of memory entries to `.claude/MEMORY/`:

- **Patterns** (`.claude/MEMORY/patterns/`) - Generalized Knowledge
- **Episodes** (`.claude/MEMORY/episodes/`) — Task-specific evidence

---

## Running the Tool

`run_clustered_requirements_batch_claude.py` runs a batch of refactoring tasks from an Excel workbook.

### Environment setup

Set your Anthropic API key in the environment or in a `.env` file at the project root:

```bash
export ANTHROPIC_API_KEY=...
```

or in `.env`:

```
ANTHROPIC_API_KEY=...
```

### Usage

```bash
# Run from task 1 to the end with Claude-Sonnet-4.6
python agents/run_clustered_requirements_batch_claude_cli.py --start 1 --count 120 --model claude-sonnet-4-6
```

### Flags

| Flag | Default | Description |
|---|---|---|
| `--excel` | `wrighthashADL/new_clustered_requirements.xlsx` | Path to the requirements workbook |
| `--start` | `1` | 1-based row index to start from |
| `--count` | `5` | Number of instances to run |
| `--model` | `claude-sonnet-4-6` | model to use |


---

## Output

Results are written incrementally to an Excel workbook (sheet: `summary`).

| Column | Description |
|---|---|
| `Instance` | Row index in the source workbook |
| `System` | ADL system name (e.g. `eshop`, `rideshare`) |
| `Requirement` | Full requirement text |
| `ValidOrInvalid` | Final verification outcome: `valid`, `invalid`, or `not_recorded` |
| `VerificationLoopCount` | Number of verification + repair rounds used |
| `ExecutionTimeSeconds` | Wall-clock time for the instance |
| `CostUSD` | API cost reported by Claude Code CLI |
| `FinalADL` | Final refactored Wright# ADL |
