---
name: refactoring-agent
description: Wright# ADL refactoring workflow — generate assertions (all property types), produce refactored ADL, apply static analysis tools, verify, fix with a capped verification loop, and write structured log.
---

# RefactoringAgent Skill

Perform the full refactoring and verification workflow: assertion generation (all property types), refactored ADL design, static analysis tool application, verification, capped fix loop, and structured logging. Use only Bash heredoc for tmp/ files.

## Important (MUSTKNOW)

MUSTKNOW 1. `tmp/` is relative to the **project root**. Use **only** Bash heredoc for all tmp/ files — never the Write tool. E.g. `cat > tmp/refactored.adl << 'EOF' ... EOF`.
MUSTKNOW 2. Verify command (from project root): `python3 agents/verification/verify_wrighthash_all_properties.py 2>&1`
MUSTKNOW 3. All intermediate reasoning, tool outputs, and decisions must be appended verbatim to `tmp/log.md`.
MUSTKNOW 4. The original ADL is valid. If verification fails, it is a refactored ADL issue.
MUSTKNOW 5. Allowed files: `tmp/assertions.md`, `tmp/refactored.adl`, `tmp/analysis_errors.md`, `tmp/log.md`, and files under `.claude/tools/` and `.claude/skills/`.
MUSTKNOW 6. YOU NEED TO follow the workflow step by step, there are 7 STEPS, DO NOT SKIP ANY STEP till then END. 
MUSTKNOW 7. Verification is capped at **4 total attempts** per run, including the first Step 4 verification. After the 4th verification attempt, stop fixing even if the result is still invalid, keep the current `tmp/refactored.adl`, and continue to Steps 6 and 7.
MUSTKNOW 8. **NEVER embed assert statements in `tmp/refactored.adl`.** Assertions belong ONLY in `tmp/assertions.md`. The verifier preserves all ADL text verbatim in every partial system it generates — embedded asserts appear in ALL partial systems (unfiltered), causing PAT to error on missing components. The `check_adl_no_asserts` tool catches this before verification.

## Workflow

### Step 0 — Retrieve relevant experience

- Launch a **MemoryAgent** subagent to retrieve relevant past experience (patterns) by invoking the **retrieval** skill.

### Step 1 — Generate assertions and save
- Analyse the ADL design and the refactoring requirement (from the prompt).
- Write assertions, one per line. There are four supported types:

  **Type 1 — Liveness** (something must eventually happen):
  ```
  assert <sys> |= [] (<Component.port.event> -> <> <Component.port.event>);
  ```
  Use when: a request at a source component must eventually reach a sink component.

  **Type 2 — Safety absence** (something must never happen):
  ```
  assert <sys> |= [] (!<Component.port.event>);
  ```
  Use when: a particular event must never occur (e.g., data leak, unauthorised access).

  **Type 3 — Conditional absence** (if A happens, B must never happen):
  ```
  assert <sys> |= [] (<Component.port.event> -> !<Component.port.event>);
  ```
  or stronger: `assert <sys> |= [] (<Component.port.event> -> [] (!<Component.port.event>));`

  **Type 4 — Prerequisite / until** (B must not happen until A happens first):
  ```
  assert <sys> |= (!<Component.port.event>) U (<Component.port.event>);
  ```
  or global: `assert <sys> |= [] ((!<Component.port.event>) U (<Component.port.event>));`

  Rules: Extract system name from the `system` block; events from `port name() = EVENT -> name();`; trace paths through connectors; generate liveness (Type 1) for each source-to-sink path; generate safety (Types 2–4) for sensitive/auth/authorisation as appropriate; each assertion MUST end with a semicolon.

- Save with heredoc:
  ```bash
  cat > tmp/assertions.md << 'EOF'
  <generated assertions>
  EOF
  ```
  If **user-provided assertions** are in the prompt under "User-provided assertions", append:
  ```bash
  cat >> tmp/assertions.md << 'EOF'
  <user-provided assertions>
  EOF
  ```
### Step 2 — Produce refactored ADL

Analyze the past experience and generated assertions. Then, look for skills starting with prefix 'reusableskill', which are distilled from past cases to handle potential violations and could be relevant to refactoring. With the past experience, assertions, and relevant reusable skills, you could design a complete, syntactically correct refactored ADL to meet the new requirements. Write it inside a fenced code block first, then save:
```bash
cat > tmp/refactored.adl << 'EOF'
<full refactored ADL>
EOF
```

### Step 3 — Apply static analysis tools

Read `.claude/tools/tools.md` first.
- If the tools table is empty (no tool rows), **skip this step**.
- Otherwise, use the **Skill tool** to invoke `wrighthash-tool-apply` and follow its full workflow (it uses `.claude/tools/tools.md` as the canonical tool list).

This skill handles the per-tool loop (run → manual analysis → cross-check → fix). The skill already knows how to:
- **Case B (tool wrong):** Launch the **ToolAgent** subagent to fix the tool, wait for confirmation, then re-run.
- **Case A (you were wrong):** record in `tmp/analysis_errors.md` AND Launch the **MemoryAgent** subagent to invoke the distill skill to record the mistake. 

After the tool applied, go to next step for verification


### Step 4 — Verify

```bash
python3 agents/verification/verify_wrighthash_all_properties.py 2>&1
```

### Step 5 — Fix loop

If verification reports invalid: diagnose, fix `tmp/refactored.adl`, re-run Step 4.
- Allow at most **4 total verification attempts** across Step 4 and all retries.
- If verification becomes valid before the cap, continue normally.
- If the 4th verification attempt is still invalid, stop fixing immediately and continue to Steps 6 and 7 with the current artifacts and outcome.
When fixing, pay attention to five rules:


### Step 6 — Finalize `tmp/log.md`

Use `tmp/log.md` as the only run log.

- Do **not** read from or copy any file under `agents/refactoring_results/`.
- If the runtime already mirrors the live transcript into `tmp/log.md`, keep using that file as-is.
- If you need to add a final summary, append only the current run's key outcome, tool results, verification status, and fix decisions to `tmp/log.md`.

### Step 7: Launch the **MemoryAgent** subagent to invoke post-reflection SKILL. Wait for the MemoryAgent subagent to complete.
