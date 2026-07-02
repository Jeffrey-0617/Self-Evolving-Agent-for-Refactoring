---
name: wrighthash-tool-apply
description: Applies Wright# ADL static analysis tools to tmp/refactored.adl, cross-checks results with independent manual analysis, resolves any discrepancy, updates skill docs with new failure cases; invoke during Wright# refactoring to validate the refactored ADL.
---

# Wright# Tool Application

Apply each static analysis tool to the refactored ADL, validate results against independent manual analysis, resolve discrepancies, and keep skill documentation up to date.

## Prerequisites
- Refactored ADL at `tmp/refactored.adl`
- Tools at `.claude/tools/<tool_name>/<tool_name>.py`
- Tool skill docs at `.claude/skills/<tool-skill-name>/SKILL.md`
- Tool summary table at `.claude/tools/tools.md` (use this as the canonical list of which tools to run)

---

## Important
MUSTKNOW 1. Always invoke the tool's skill before running it — never run the tool without loading its skill first.
MUSTKNOW 2. Manual analysis must be done independently and recorded before comparing with tool output — do not let the tool result bias your analysis.
MUSTKNOW 3. Judge the tool result by what it **prints**, not the exit code alone. A valid PASS result must print a message that clearly and unambiguously states success — e.g. "No violations found" or "All checks passed". Any message containing "failed", "error", "Error", or any ambiguous/contradictory wording is **NOT** a valid pass — treat it as a disagreement and go to Case B. For example: "All port name checks failed." is NOT a pass even if exit code is 0 — "failed" in the message means the tool output is wrong or confused.
MUSTKNOW 4. Never patch a tool ad hoc — always fix via the full generation workflow (test cases → fix → all tests pass → update SKILL.md).
MUSTKNOW 5. Always **append** new failure cases to a SKILL.md; never overwrite existing content.
MUSTKNOW 6. Process tools **one at a time** — complete Steps 1–5 fully for a tool (including any fixing) before starting the next tool. Never run all tools in the table first and fix later.

## Workflow

For **each tool** listed in `.claude/tools/tools.md`, complete **all** Steps 1–5 below before moving to the next tool. Do NOT run multiple tools in advance.

### Step 1 — Invoke the tool's skill

Use the **Skill tool** to invoke the tool's named skill (e.g. `check-port-names`). This loads the rule definition, usage, and known failure cases into context.

### Step 2 — Run the tool

```bash
python3 .claude/tools/<tool_name>/<tool_name>.py tmp/refactored.adl; echo "Exit code: $?"
```

Record the exact output and exit code. Do not act on it yet.

### Step 3 — Independent manual analysis

**Before comparing with the tool output**, manually inspect `tmp/refactored.adl` for violations of this rule using the rule definition from Step 1. Record your finding independently:
- **Pass** or **Fail**
- If fail: identify which component/port/role is violated and why

### Step 4 — Cross-check tool result vs manual analysis, resolve disagreements and fix violations

Compare the tool result (Step 2) against the manual analysis (Step 3):

**If they agree — both pass:**
→ Go to Step 5.

**If they agree — both fail:**
→ Fix `tmp/refactored.adl` to resolve the violation.
→ Re-run the tool to confirm it now reports no violations.
→ If violations are still reported, repeat the fix and re-run until the tool passes.
→ Then go to Step 5.

**If they disagree:**
1. Re-read the rule definition carefully from the tool's skill (loaded in Step 1).
2. Re-examine `tmp/refactored.adl` with fresh eyes.
3. Determine the root cause:

   **Case A — You were wrong:**
   The tool result is correct and your manual analysis was incorrect.
   → Record the mistake in `tmp/analysis_errors.md`: note which rule, what you misread, and why the tool is right.
   → Trust the tool result: if tool passed → go to Step 5; if tool failed → fix `tmp/refactored.adl`, re-run the tool to confirm it reports no violations, then go to Step 5.

   **Case B — Tool is wrong:**
   Your manual analysis is correct and the tool produced a wrong result.
   → Use the **Skill tool** to invoke `wrighthash-tool-gen` and follow its full generation process:
     1. Create test cases that expose the bug (`.claude/tools/<tool_name>/testcases/example<N>.adl`)
     2. Fix the tool in `.claude/tools/<tool_name>/<tool_name>.py`
     3. Run ALL test cases until every one passes
     4. Update the tool's SKILL.md with the fixed behaviour
   → After the fixed tool passes all tests, re-run it on `tmp/refactored.adl` and return to Step 3.

### Step 5 — Update the skill and move on

If a new failure case was encountered during this tool's run that is **not already documented** in its SKILL.md: append it under `## Failure Cases` using the template format from `wrighthash-tool-gen`.

Then move to the next tool. If this turn is the last tool, then returning to continue the main refactoring workflow.

