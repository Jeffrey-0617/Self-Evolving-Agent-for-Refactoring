# Wright# Refactoring Agent

This repository contains a Claude Code based Wright# ADL refactoring workflow with:

- a subscription-backed refactoring entry point
- verification and repair loops
- evolving memory, tools, and reusable skills under `.claude/`
- a batch runner for clustered requirement experiments

## Main Entry Points

Recommended single-run entry point:

```bash
python3 agents/refactoring_agent_subscription.py \
  --model claude-sonnet-4-6 \
  --adl eshop \
  --requirement "Add a loyalty rewards system" \
  --language-type wrighthash
```

Batch runner for clustered requirements:

```bash
python3 agents/run_clustered_requirements_batch.py
```

The original API-key-based agent still exists at [agents/refactoring_agent.py](agents/refactoring_agent.py), but the current recommended path is the subscription-backed agent at [agents/refactoring_agent_subscription.py](agents/refactoring_agent_subscription.py).

## Refactoring Workflow

The runtime workflow is driven primarily by [refactoring-workflow/SKILL.md](.claude/skills/refactoring-workflow/SKILL.md):

1. Retrieve relevant experience from `.claude/MEMORY/`.
2. Generate assertions into `tmp/assertions.md`.
3. Produce a refactored ADL into `tmp/refactored.adl`.
4. Apply registered static analysis tools from `.claude/tools/tools.md`.
5. Verify with [verify_wrighthash_all_properties.py](agents/verification/verify_wrighthash_all_properties.py).
6. Repair and re-verify, but stop after 4 total verification attempts.
7. Finalize `tmp/log.md` for the current run and trigger post-reflection.

Assertion policy:
- `tmp/assertions.md` is generated in Step 1 and may be refined later if needed during repair attempts.

The subscription agent also records:

- verification outcome
- verification loop count
- cost and duration from the existing usage tracker
- the live run transcript in `tmp/log.md`

## Batch Experiment Output

[run_clustered_requirements_batch.py](agents/run_clustered_requirements_batch.py) runs the first `N` rows from `wrighthashADL/new_clustered_requirements.xlsx` and writes progress after each completed instance.

The summary workbook contains one row per instance with:

- `ValidOrInvalid`
- `VerificationLoopCount`
- `ExecutionTimeSeconds`
- `CostUSD`
- `SkillTrace`
- `Assertions`
- `FinalADL`

For batch runs, the persisted output is the summary workbook under `agents/batch_results/`.

## Knowledge System

The `.claude/` directory is the long-term knowledge layer for this workflow.

### Memory

Source of truth:

- [MEMORY.md](.claude/MEMORY/MEMORY.md)
- `.claude/MEMORY/patterns/*.md`
- `.claude/MEMORY/episodes/*.md`

Main skills:

- [retrieval](.claude/skills/retrieval/SKILL.md): load the most relevant prior patterns at task start
- [distill](.claude/skills/distill/SKILL.md): record mid-task analysis mistakes
- [post-reflection](.claude/skills/post-reflection/SKILL.md): turn the finished run into generalized patterns and episodes

### Tools

Source of truth:

- [tools.md](.claude/tools/tools.md)
- `.claude/tools/<tool_name>/<tool_name>.py`
- `.claude/tools/<tool_name>/testcases/*.adl`

Main skills:

- [wrighthash-tool-apply](.claude/skills/wrighthash-tool-apply/SKILL.md)
- [wrighthash-tool-gen](.claude/skills/wrighthash-tool-gen/SKILL.md)

### Skills

Source of truth:

- [skillsummary.md](.claude/skills/skillsummary.md)
- `.claude/skills/*/SKILL.md`

Skills fall into three practical groups:

- workflow skills such as `refactoring-workflow`
- reusable design guidance skills such as `reusableskill-*`
- tool-oriented skills such as `check-*`, `wrighthash-tool-apply`, and `wrighthash-tool-gen`

## Metadata for Retrieval and Management

The current skill instructions now emphasize a small set of metadata fields that give the most value without making the memory system heavy.

### Pattern metadata

- `scope`: helps rank assertion vs connector vs tool vs workflow lessons
- `status`: lets retrieval prioritize active lessons and deprioritize stale ones
- `confidence` and `references`: express how trustworthy and repeated the lesson is
- `skill_ref` and `tool_ref`: connect a memory to its operational form

### Episode metadata

- `task_type`: helps match similar tasks
- `first_pass_success`: distinguishes clean successes from repair-heavy runs
- `skills_used` and `tools_used`: shows what actually helped

### Skill summary metadata

- `kind`: reusable skill vs workflow vs tool-check vs tool-gen
- `scope`: what area the skill applies to
- `linked_patterns`: which memories it operationalizes
- `status`: active vs deprecated guidance

These fields improve three things:

1. Retrieval ranking
2. Knowledge update quality
3. Long-term maintenance of memories and skills

See the full graph and explanation here:
[docs/retrieval-metadata-graph.md](docs/retrieval-metadata-graph.md)

## File Map

| Path | Purpose |
|---|---|
| [agents/refactoring_agent_subscription.py](agents/refactoring_agent_subscription.py) | Subscription-backed single-run refactoring agent |
| [agents/run_clustered_requirements_batch.py](agents/run_clustered_requirements_batch.py) | Batch runner with one-row-per-instance XLSX output |
| [agents/verification/verify_wrighthash_all_properties.py](agents/verification/verify_wrighthash_all_properties.py) | Verification engine |
| [tmp/assertions.md](tmp/assertions.md) | Current assertions |
| [tmp/refactored.adl](tmp/refactored.adl) | Current refactored ADL |
| [tmp/log.md](tmp/log.md) | Structured run log for post-reflection |
| [.claude/MEMORY/MEMORY.md](.claude/MEMORY/MEMORY.md) | Memory index |
| [.claude/skills/skillsummary.md](.claude/skills/skillsummary.md) | Skill index |
| [.claude/tools/tools.md](.claude/tools/tools.md) | Tool index |

## Current Direction

The repo is now set up around a simple loop:

1. use memory and reusable skills early
2. use tools before verification when possible
3. verify and repair until valid
4. distill the run back into memory and skills

That makes the system progressively better at future Wright# refactoring tasks without replacing markdown as the source of truth.
