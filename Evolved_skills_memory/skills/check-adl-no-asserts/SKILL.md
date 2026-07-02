---
name: check-adl-no-asserts
kind: tool
scope: verification-workflow
description: Checks that a Wright# ADL file contains no embedded assert statements — asserts must be in tmp/assertions.md only, not in the ADL file, to avoid PAT errors during partial-system verification.
linked_patterns: [adl-file-no-assert-statements]
status: active
---

# check-adl-no-asserts Tool Skill

## Purpose

Run this tool as the **first static analysis step** on any refactored ADL before formal verification. It detects embedded `assert` statements in the ADL file and flags them as errors.

## Why This Matters

The Wright# verifier (`verify_wrighthash_all_properties.py`) reads assertions from `tmp/assertions.md` and uses them with a path-filtering mechanism — it sends only the relevant assertion for each partial system to PAT. However, its `update_adl_with_new_attachments()` function preserves ALL original text from `tmp/refactored.adl` verbatim when building each partial system. Any `assert` statements embedded in the ADL file therefore appear in EVERY partial system, bypassing the path filter. PAT then encounters assertions referencing components that do not exist in the current partial system and reports "An error has occurred." for every assertion.

**Root cause in one sentence:** Assertions in the ADL file are not filtered by the verifier — only assertions in `tmp/assertions.md` are filtered.

## Usage

```bash
python3 .claude/tools/check_adl_no_asserts/check_adl_no_asserts.py tmp/refactored.adl
```

- Exit 0: ADL file is clean — no assert statements present.
- Exit 1: Assert statements found — lists line numbers and content. Remove them from the ADL and place them in `tmp/assertions.md`.

## When to Invoke

Invoke immediately after writing `tmp/refactored.adl`, before running any other static analysis tool or the formal verifier. The check is cheap and prevents a hard-to-diagnose category of PAT errors.

## Failure Cases

| Symptom | Cause | Fix |
|---|---|---|
| PAT reports "An error has occurred." on every partial system | Assert statements embedded in ADL file | Remove asserts from ADL, ensure they are in tmp/assertions.md only |
| All assertions marked INVALID despite seemingly correct design | Same root cause as above | Same fix |

## Running Tests

```bash
python3 .claude/tools/check_adl_no_asserts/check_adl_no_asserts.py --test
```

All 5 test cases must pass before deploying changes to the tool.
