# Self-Evolving Agent for Software Architecture Refactoring

This repository implements a self-evolving LLM agent that refactors software architecture designs based on natural-language functional requirements. The agent is **self-evolving**: it starts with a fixed set of cold-start skills and no memory, and accumulates reusable knowledge across tasks.

---

## Agent Knowledge

### Cold-start Skills
The agent starts with a set of cold-start skills in [`.claude/skills/`](.claude/skills/). These are available from the very first task:

| Skill | Purpose |
|---|---|
| `refactoring-workflow` | Defines the Essential workflow of the agents: generate assertions, refacor designs, verify, repair |
| `retrieval` | Retrieve relevant memory before starting a task |
| `post-reflection` | After a task, distill the run log into reusable memory entries and update skills |
| `wrighthash-tool-apply` | Apply static analysis tools|
| `wrighthash-tool-gen` | Create or update static analysis tools |
| `distill` | Record a mistake pattern during the task |

### Evolving Memory and Skills
As the agent completes tasks, it writes new evolved skills, tools, and memory. These can be found at [`Evolved_skills_memory/`](Evolved_skills_memory/README.md). This folder captures everything the agent has learned across all runs:

- **Skills** — new skills created during tasks can be found at [`Evolved_skills_memory/skills/README.md`](Evolved_skills_memory/skills/README.md). To illustrate what generated skills are, examples can be found at [`Evolved_skills_memory/skills/check-port-name-uniqueness/SKILL.md`](Evolved_skills_memory/skills/check-port-name-uniqueness/SKILL.md) and [`Evolved_skills_memory/skills/reusableskill-connector-rules/SKILL.md`](Evolved_skills_memory/skills/reusableskill-connector-rules/SKILL.md).
- **Tools** — static analysis Python scripts associated with the script-based skills can be found at [`Evolved_skills_memory/tools/README.md`](Evolved_skills_memory/tools/README.md).
- **Memory patterns** — generalised reusable knowledge extracted from completed tasks.
- **Memory episodes** — concrete task-specific evidence.
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

### PAT verifier setup

Before running the agent, set up the PAT verifier with the Wright# modules and deploy it as a service. Then, update the verifier endpoint in [`agents/verification/verify_wrighthash_all_properties.py`](agents/verification/verify_wrighthash_all_properties.py), and make sure the port matches the deployed PAT service:

```python
url = "http://0.0.0.0:<PORT>/api/adlapi/verify"
```

Replace it with the actual PAT service port before running the batch script.

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
