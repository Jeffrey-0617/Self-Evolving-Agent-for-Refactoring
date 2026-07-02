---
name: distill
description: Record an analysis-mistake pattern when a rule was misread during tool application (mid-task). Distill the mistake into .claude/MEMORY.
---

# Distill

Run **mid-task** when a rule was misread during tool application. Distill it into an `analysis-mistake` pattern in `.claude/MEMORY/` without duplicating existing entries.

## MUSTKNOW

- Memory store: `.claude/MEMORY/`. Index: `.claude/MEMORY/MEMORY.md`. Patterns: `.claude/MEMORY/patterns/<slug>.md`.
- **Dedup before writing.** Check MEMORY.md for an existing pattern of type `analysis-mistake` with matching tags. If one exists → update it; never create a duplicate.
- Raw logs are not stored here; only distilled patterns.

## Pattern file format (analysis-mistake)

`.claude/MEMORY/patterns/analysis-mistake-<slug>.md`:

```markdown
---
id: p-XXX
type: analysis-mistake
scope: tool | verification | connector | component | workflow | assertion | architecture
status: active
tags: [tag1, tag2]
confidence: low | medium | high
references: 1
skill_ref: .claude/skills/<name>/SKILL.md   # optional
tool_ref: .claude/tools/<tool_name>/<tool_name>.py   # optional
---

## Context
When this mistake applies.

## Distilled Rule
The correct interpretation of the rule.

## Example
Concrete example (generalised names).

## Anti-pattern
What was misread and why it fails.
```

## Steps

1. Read the **mistake details**: which rule, what was misread, the correct interpretation.
2. **Dedup check**: search MEMORY.md for a pattern of type `analysis-mistake` with matching tags.
   - If a similar entry exists: update the existing pattern file (increment `references`, keep `status: active`, refresh `skill_ref` / `tool_ref` if the lesson now maps to an operational artifact, add the new instance as a note). Do NOT create a duplicate.
   - If no match: create `.claude/MEMORY/patterns/analysis-mistake-<slug>.md` and add a row to the Patterns table in MEMORY.md. Include the most specific `scope` you can infer because retrieval should use it for ranking.
3. No reply required — fire-and-record.
