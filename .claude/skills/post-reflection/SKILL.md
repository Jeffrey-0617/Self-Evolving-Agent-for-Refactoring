---
name: post-reflection
description: After a refactoring task, distill tmp/log.md into .claude/MEMORY (patterns and episodes), generalize into reusable rules, and create/update SKILLs; update the index.
---

# Post-Reflection

Run **after a refactoring task** when `tmp/log.md` exists. Distill the log into **patterns** and an **episode**; **generalize** patterns into reusable rules; **create or update reusable SKILL.md** when appropriate; update `.claude/MEMORY/`.

## MUSTKNOW1

- Memory store: `.claude/MEMORY/` (project root). Subdirs: `patterns/`, `episodes/`. Create if missing.
- Index: `.claude/MEMORY/MEMORY.md`. Keep under 150 lines. Tables: **Patterns**, **Episodes**. Prefer lightweight retrieval metadata in the index so future runs can rank memories without reopening every file.
- **Dedup before writing.** If a similar entry exists in MEMORY.md or in `patterns/`, `episodes/` → update it (increment references, raise confidence); NEVER DUPLICATE.
- Raw logs (`tmp/log.md`) are source only — always distill to a pattern (never store the log as-is).
- **Generalize the created patterns and create Reusable SKILLs.** When a pattern is sufficiently reusable, create or update `.claude/skills/<reusableskill-name>/SKILL.md` and add an entry to `.claude/skills/skillsummary.md` with the same description as in that SKILL.md. Do NOT keep requirement-specific or ADL-specific details. Express rules in reusable form so they apply to future refactoring tasks. Record only the highest-value metadata needed for retrieval and management: pattern `scope`, `status`, `confidence`, `references`, and `skill_ref` / `tool_ref`; episode `task_type`, `first_pass_success`, `skills_used`, and `tools_used`; skill summary `kind`, `scope`, `linked_patterns`, and `status`.

## MUSTKNOW2: How to check for duplicates

- **Use the index first.** Check MEMORY.md (Patterns table: at minimum id, tags, summary; preferred metadata when present: `scope`, `status`, `confidence`, `references`, `skill_ref`, `tool_ref`; Episodes table: at minimum id, task, outcome; preferred metadata when present: `task_type`, `first_pass_success`, `skills_used`, `tools_used`) and `.claude/skills/skillsummary.md` (at minimum skill name + description; preferred metadata when present: `kind`, `scope`, `linked_patterns`, `status`). Match by meaning: same or very similar topic, tags, scope, or description → treat as existing.
- **Open the file only when likely a match.** If the index/summary suggests the same or very similar entry, then read that pattern or SKILL file to confirm. If confirmed → update it (increment references, merge content); do not create a new file.
- **Never create a duplicate.** When in doubt, prefer updating an existing entry over creating a new one.

## File format: Pattern (all use this structure)

**Pattern** (`.claude/MEMORY/patterns/<slug>.md`): frontmatter `id`, `type`, `scope`, `status`, `tags`, `confidence`, `references`; sections **Context**, **Distilled Rule**, **Example**, **Anti-pattern**. Optional: `skill_ref: .claude/skills/<name>/SKILL.md` and `tool_ref: .claude/tools/<tool_name>/<tool_name>.py` when a reusable SKILL or tool was created.

- Use for design rules (connector choices, role rules, naming, etc.) and for error→repair lessons (tool/verifier errors fixed): same structure — Context (when this applies), Distilled Rule (what to do), Example (minimal illustration), Anti-pattern (what went wrong / what to avoid).
- Types: prefer operational types such as `design-pattern`, `verification-pattern`, `repair-pattern`, `tool-debug-pattern`, or `analysis-mistake` when they fit better than coarse labels.

**Episode** (`.claude/MEMORY/episodes/ep-<N>.md`): frontmatter `id`, `task`, `task_type`, `outcome`, `first_pass_success`, `date`, `patterns_extracted`, `skills_used`, `tools_used`; section Summary.

**Index** (MEMORY.md): **Patterns** (at minimum: id, type, tags, summary, file; preferred additions: scope, status, confidence, references, skill_ref, tool_ref), **Episodes** (at minimum: id, task, outcome, key_patterns_used, file; preferred additions: task_type, first_pass_success, skills_used, tools_used).
**Skill Summary** (`.claude/skills/skillsummary.md`): at minimum `skill name`, `description`; preferred additions: `kind`, `scope`, `linked_patterns`, `status`.

MUSTKNOW 3: Every generalized rule must either (a) become an automated **tool** (preferred, so future refactored ADLs can be checked before verification). For example, if you encountered the problem stated in RULE 1 "Port names must be unique (within each component and across all components) and differ from their own event names", then you definately can convert it into a script, or (b) become a **reusable SKILL rule** when it is not automatable (e.g. design guidance rather than a syntactic/structural constraint).

## Steps

1. Read `tmp/log.md` in full.

2. **Distill and generalize patterns** (connector choices, role rules, coupling direction, naming, integration topology):
   - **Analyse** each candidate: what is the abstract rule? (Input role vs output role? Connector type? Port attachment? Assertion type?) 
      Here are some references to support analyse, issues mostly arise from the follows:
         Wrighthash Syntax Rules:
            Rule 1: Port names must be unique (within each component and across all components) and differ from their own event names
            Rule 2: Each input role of a connector instance can only be attached to one component port
            Rule 3: One component port can only be attached to at most one input role
            Rule 4: Every declared connector instance must have all its roles attached (no incomplete attachments)
            Rule 5: Role names in attach statements must match connector definitions exactly
            Rule 6 (Attach ordering): In a <*> multi-role attachment, at most one input role is allowed, and it must appear before all output roles.       


            Connector Semantics, espeically the input and output roles:
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
            - requester hits process first →  requester's attached component port executes
            - requester sends req!j
            - responder receives req?j, triggers invoke
            - responder hits process → responder's attached component port executes
            - responder sends res!j, requester receives res?j

   - **Generalize:** Remove requirement-specific names and examples. Express as reusable rules (e.g. "Input role: can attach to …; cannot … . Output role: …").
   - Dedup in MEMORY.md. If similar exists → update. If new → create `.claude/MEMORY/patterns/<slug>.md` with the **generalized** rule and add to index. Always set the narrowest useful `scope` and default new lessons to `status: active`.
   - **If the generalized rule is reusable:** 
      -- Assess whether the rule can be converted into a Wright# ADL static analysis script (most syntax and semantic rules related issues can be converted into scripts to for further refactoring task, NEVER HARDCODING) (e.g. structural checks on components, connectors, ports, roles, attach statements). If it can be automated and no such tool for the rule: either extend an existing tool script (when the new rule is strongly similar to an existing tool’s scope) or create a new tool (when it is distinct). In both cases, follow **wrighthash-tool-gen** to ensure testcases are added and the associated skill created or updated; tool script lives at `.claude/tools/<tool_name>/<tool_name>.py` and the associated skill at `.claude/skills/<tool-skill-name>/SKILL.md`.
      -- If the rule cannot be converted to a script (e.g. design guidance, qualitative decisions): create or update `.claude/skills/<reusableskill-name>/SKILL.md` (e.g. `reusableskill-connector-rules`, `reusableskill-input-output-roles`). The skill should contain the generalized rules, usage guidance, and optional examples — not the original concrete requirement.
      -- Add `skill_ref` or `tool_ref` to the pattern frontmatter and update `.claude/skills/skillsummary.md`. When creating a new `reusableskill-*` or a new tool skill, add an entry to skillsummary.md and include `kind`, `scope`, `linked_patterns`, and `status` when the summary table already supports those columns.


3. **Write episode**: create `.claude/MEMORY/episodes/ep-<N>.md`. Add a row to the Episodes table in MEMORY.md. Record `task_type`, `first_pass_success`, `skills_used`, and `tools_used` when they can be inferred reliably from the run.

4. **Update index**: Ensure MEMORY.md reflects all new/updated patterns and the new episode. Keep under 150 lines; merge similar entries.

