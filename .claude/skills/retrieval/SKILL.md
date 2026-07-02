---
name: retrieval
description: Load relevant patterns from .claude/MEMORY for the current task (e.g. at task start).
---

# Retrieval

Run at **task start** when you need prior experience for the current task. Load relevant patterns from `.claude/MEMORY/` and summarise them.

## MUSTKNOW

- Memory store: `.claude/MEMORY/` (relative to project root). Index: `.claude/MEMORY/MEMORY.md`.
- Index has two tables: **Patterns** (at minimum: id, type, tags, summary, file; preferred metadata when present: `scope`, `status`, `confidence`, `references`, `skill_ref`, `tool_ref`, `last_used`), **Episodes** (at minimum: id, task, outcome, key_patterns_used, file; preferred metadata when present: `task_type`, `first_pass_success`, `skills_used`, `tools_used`).
- Pattern files live in `.claude/MEMORY/patterns/<slug>.md`. Episode files in `.claude/MEMORY/episodes/ep-<N>.md`.

## Steps

1. Read `.claude/MEMORY/MEMORY.md`.
2. Match entries to the **task description** (requirement + component names mentioned). Prefer patterns whose `scope` matches the current task focus (e.g. assertion, connector, component, architecture, tool, workflow), whose `status` is `active`, and whose confidence / references suggest repeated success.
3. Prefer patterns that already link to an operational artifact (`skill_ref` or `tool_ref`) and episodes whose `task_type`, `skills_used`, or `tools_used` are similar to the current task. Based on the `.claude/MEMORY/MEMORY.md` description, select at most relevant **5 pattern files** to stay within context budget.
4. Summarise each selected pattern (distilled rule + anti-pattern).
5. If nothing matches or MEMORY.md is empty, output: **"No relevant memories found — proceeding fresh."**
