---
id: adl-file-no-assert-statements
type: repair-pattern
scope: verification-workflow
status: active
tags: [assert, ADL-file, verifier, PAT, partial-system, assertions.md, verification-failure]
confidence: 0.98
references: 41
tool_ref: .claude/tools/check_adl_no_asserts/check_adl_no_asserts.py
---

## Context

When using `verify_wrighthash_all_properties.py`, assertions are read from `tmp/assertions.md`. The verifier's `update_adl_with_new_attachments()` function reconstructs partial ADL systems by preserving ALL original text from `tmp/refactored.adl` verbatim in every partial system it generates. If `assert` statements are embedded in `tmp/refactored.adl`, they appear unfiltered in EVERY partial system sent to PAT — including partial systems that do not contain the components referenced in those assertions. PAT then errors with "An error has occurred." on every partial system, causing all assertions to be marked invalid.

## Distilled Rule

`tmp/refactored.adl` must NOT contain any `assert` statements. All assertions belong ONLY in `tmp/assertions.md`. The verifier reads assertions from `assertions.md` and applies path-filtering per partial system; any `assert` text in the ADL file bypasses this filtering entirely.

Run `check_adl_no_asserts` as the first static analysis step to catch this before submitting for formal verification.

## Example

**Incorrect — assert embedded in ADL file (tmp/refactored.adl):**
```wright
system lifenet {
  ...
  execute ...;
}

-- DO NOT include assert statements here:
assert lifenet |= [] (ComponentA.port.event -> <> ComponentB.port.event);
```

**Correct — ADL file contains only system declaration; assertions in separate file:**
```
# tmp/refactored.adl
system lifenet {
  ...
  execute ...;
}
# (no assert statements)

# tmp/assertions.md
assert lifenet |= [] (ComponentA.port.event -> <> ComponentB.port.event);
```

## Anti-pattern

Placing `assert` statements at the end of `tmp/refactored.adl` (e.g., for convenience or cross-referencing). This silently injects all assertions into every partial ADL the verifier generates, causing PAT to error on references to absent components. The error message ("An error has occurred.") does not clearly point to the root cause, making this failure mode hard to diagnose without knowing the verifier internals.
