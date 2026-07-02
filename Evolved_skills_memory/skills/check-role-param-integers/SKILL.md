---
name: check-role-param-integers
kind: tool
scope: connector-role-attach
description: Checks Wright# ADL attach statements for non-integer connector role parameters — every parameterised role (publisher, requester, writer, reader, extsupplier, querier, forwarder) must use a unique integer literal; letter identifiers cause PAT to return "An error has occurred." for all partial systems.
linked_patterns: connector-role-parameter-must-be-integer
status: active
tool: .claude/tools/check_role_param_integers/check_role_param_integers.py
---

# check-role-param-integers

Static analysis tool that verifies every parameterised connector role in a Wright# ADL file uses an integer literal as its parameter value.

## What It Checks

Connector output roles that carry a data parameter — `publisher(j)`, `requester(j)`, `writer(j)`, `reader(j)`, `extsupplier(j)`, `querier(j)`, `forwarder(j)`, `sender(j)` — must be instantiated with an **integer literal** in every `attach` statement and port-body expression. Using a letter or symbolic identifier (e.g. `b`, `v`, `mm`, `cr`, `t`, `i`, `j`) instead causes PAT to report "An error has occurred." for **all** partial systems, failing verification completely.

Input roles (`responder`, `writestorage`, `blockstorage`, `subscriber`, `receiver`) take no parameter and are not checked.

## When to Run

Run this tool as part of the standard three-tool static analysis check, before submitting to the PAT verifier:

```
python3 .claude/tools/check_adl_no_asserts/check_adl_no_asserts.py tmp/refactored.adl
python3 .claude/tools/check_port_name_uniqueness/check_port_name_uniqueness.py tmp/refactored.adl
python3 .claude/tools/check_assertion_events/check_assertion_events.py tmp/refactored.adl tmp/assertions.md
python3 .claude/tools/check_role_param_integers/check_role_param_integers.py tmp/refactored.adl
```

## Usage

```
python3 .claude/tools/check_role_param_integers/check_role_param_integers.py <adl_file_path>
python3 .claude/tools/check_role_param_integers/check_role_param_integers.py --test   # run self-tests
```

Exit 0: all role parameters are integer literals.
Exit 1: one or more non-integer parameters found (error lines printed with line numbers).

## Rules

1. **Integer literals only**: every parameterised role instantiation must use a plain integer, e.g. `publisher(54)`, `requester(53)`, `writer(64)`.
2. **Unique integers**: each role instantiation in the same ADL should use a distinct integer. Audit existing attach statements to find the integers already in use before assigning new ones.
3. **No symbolic names**: `publisher(b)`, `requester(j)`, `writer(mm)` are all invalid even if `j` is defined as a CSP variable in the connector definition — PAT does not accept these as role parameters in attach statements.

## Failure Modes

| Symptom | Root Cause | Fix |
|---|---|---|
| PAT returns "An error has occurred." for ALL partial systems | One or more attach statements use letter parameters for role arguments | Replace every letter parameter with a unique integer literal |
| Error indistinguishable from server-unavailability at first glance | PAT error message is identical; distinguish by grepping for `^Error occurred` (server-down pattern) — absence of that prefix means this tool's error | Run this tool to confirm |
| All 3 existing static tools (check_adl_no_asserts, check_port_name_uniqueness, check_assertion_events) PASS | Those tools do not inspect role parameter types | This tool (check_role_param_integers) is the only guard |

## Example Output

**On violation:**
```
ERROR (line 47): role 'publisher' has non-integer parameter 'b' — PAT requires integer literals for role parameters. Replace 'b' with a unique integer.
  >> attach TamperGuard.tghash() = txhashwire.publisher(b);
ERROR (line 48): role 'requester' has non-integer parameter 'i' — PAT requires integer literals for role parameters. Replace 'i' with a unique integer.
  >> attach IntegrityVerifier.ivcheck() = ivverifywire.requester(i);
```

**On success:**
```
All connector role parameters are integer literals. No violations found.
```
