---
name: wrighthash-tool-gen
description: Creates or updates Wright# ADL static analysis tools for constraint rules: add test cases, implement/fix the tool, ensure all tests pass, then draft/update the tool SKILL.md.
---

# Wright# Tool Generation & Update

Create and validate a new static analysis tool for a Wright# ADL constraint rule, **or update an existing tool** when fixing a bug or extending a rule.

## Prerequisites
- Tools stored in `.claude/tools/<tool_name>/` — one subfolder per rule, containing the script and a `testcases/` subfolder
- Skill docs stored in `.claude/skills/<skill-name>/SKILL.md`
- Test ADL files stored at `.claude/tools/<tool_name>/testcases/example<N>.adl`

## Workflow

### Step 1 — Generate test cases

For the rule being implemented, write minimal ADL test cases and save them inside the tool's `testcases/` subfolder:

- At least **2 success cases**: valid ADL that correctly follows the rule → tool must exit `0`
- At least **2 failure cases**: invalid ADL that violates the rule → tool must exit `1` with a descriptive error

Save as `.claude/tools/<tool_name>/testcases/example1.adl`, `.claude/tools/<tool_name>/testcases/example2.adl`, etc. Each file must be a complete, self-contained ADL snippet. Label each file's intended result in a comment at the top.

If you are **updating/fixing** an existing tool:
- Add **regression** testcases that reproduce the bug (at least 1 failure + 1 success if applicable).
- Keep existing testcases; do not delete them unless they are incorrect.

Example naming (for check_port_names):
```
.claude/tools/check_port_names/testcases/example1.adl  ← success: valid port names
.claude/tools/check_port_names/testcases/example2.adl  ← success: multiple components, all valid
.claude/tools/check_port_names/testcases/example3.adl  ← failure: port name matches event name
.claude/tools/check_port_names/testcases/example4.adl  ← failure: duplicate port name within a component
```

### Step 2 — Build the tool

Create or update the Python script at `.claude/tools/<tool_name>/<tool_name>.py`:
- Accepts the ADL file path as `sys.argv[1]`
- Parses the ADL and checks the rule
- Prints a descriptive error message per violation (include component/port/role names)
- Exits `0` if all checks pass, `1` if any violation found or parse error occurs
- MUSTKNOW: One TOOL per RULE — never combine multiple rule checks in one script

### Step 3 — Test the tool against all cases

Run the tool against every test case from Step 1:

```bash
python3 .claude/tools/<tool_name>/<tool_name>.py .claude/tools/<tool_name>/testcases/example1.adl
python3 .claude/tools/<tool_name>/<tool_name>.py .claude/tools/<tool_name>/testcases/example2.adl
# ... for every test case
```

Expected results:
- Success cases → exit code `0`, with a clear positive message (e.g. "All checks passed" or "No violations found")
- Failure cases → exit code `1`, error message that correctly identifies the violation

**ALL test cases must pass.** If any test produces the wrong result:
1. Diagnose the bug in the tool
2. Fix the tool
3. Re-run ALL test cases from the beginning
4. Repeat until every case passes

Do not proceed to Step 4 until all tests pass.

### Step 4 — Draft the SKILL.md

Only after ALL tests pass, create or update the skill at `.claude/skills/<tool-skill-name>/SKILL.md` using the test cases from Step 1 as concrete examples.

If you are **updating/fixing** an existing tool SKILL:
- **Append** any new failure cases under `## Failure Cases`; do not overwrite existing cases.
- Update the `## Rule` wording only if the intended rule actually changed (scope clarification).

Follow the **Tool Usage SKILL Template** below.

---

## Tool Usage SKILL Template

Use this exact structure when creating a SKILL.md for a new tool:

```markdown
---
name: <tool-slug>
description: [Third-person] Checks Wright# ADL for <rule summary>; invoke when verifying a refactored ADL against this rule. Under 200 chars.
---

# <Tool Name>

One-sentence description of the rule being enforced.

## Rule

State the rule precisely, matching the wrighthash-refactoring-basicflow documentation.

## Usage

Run from the project root:
\```bash
python3 .claude/tools/<tool_name>/<tool_name>.py <adl_file_path>
\```
- Exit 0: all checks passed
- Exit 1: violations found or parse error

## Failure Cases

### Failure 1: <short label>
**Incorrect ADL:**
\```wright
<minimal ADL snippet that triggers the violation>
\```
**Error output:**
\```
<exact tool output>
\```
**Correct ADL:**
\```wright
<fixed ADL snippet>
\```
**Explanation:** Why the fix resolves the violation.

### Failure 2: <short label>
(repeat pattern; append new cases here as they are discovered)

## Solution Patterns

### Problem: <description>
**Wrong approach:**
\```wright
<bad snippet>
\```
**Correct approach:**
\```wright
<good snippet>
\```
```

## Notes
- MUSTKNOW: One TOOL per RULE — never combine multiple rule checks in one script.
- MUSTKNOW: ALL test cases must pass before drafting the SKILL.md — no exceptions.
- MUSTKNOW: Test files (`.claude/tools/<tool_name>/testcases/example<N>.adl`) live alongside the tool; reuse them as examples in the SKILL.md.
- MUSTKNOW: The existing skills (`check-input-role-attachments`, `check-port-input-role-mapping`) may be missing frontmatter — add it when editing them.
