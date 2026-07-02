---
id: verifier-connection-error-as-invalid
type: tool-debug-pattern
scope: verification-workflow
status: active
tags: [verifier, PAT, connection-error, server-unavailable, INVALID, false-negative, HTTP]
confidence: 0.95
references: 23
skill_ref: .claude/skills/reusableskill-verification-diagnostics/SKILL.md
---

## Context

When `verify_wrighthash_all_properties.py` cannot reach the PAT server (e.g. `10.211.55.4:8090`), it catches the exception and returns the string `"error"`. The driver then treats `"error"` the same as `"invalid"` — the final output is `invalid` regardless of ADL correctness. Static analysis tools may all pass while the verifier consistently returns `invalid`.

## Distilled Rule

**Distinguish server-unavailability INVALID from genuine assertion INVALID.**

Before concluding an ADL is incorrect, check whether all verifier errors are HTTP connection failures:

```bash
python3 agents/verification/verify_wrighthash_all_properties.py 2>&1 | grep "^Error occurred"
```

If every `Error occurred:` line mentions `HTTPConnectionPool`, `ConnectTimeoutError`, `NewConnectionError`, or `Host is down`, the INVALID result is a **false negative** caused by server downtime — not an ADL defect. The ADL correctness verdict should then rest on static analysis tool results alone.

## Example

```
Error occurred: HTTPConnectionPool(host='10.211.55.4', port=8090): Max retries exceeded
  (Caused by NewConnectionError: Failed to establish a new connection: [Errno 64] Host is down)
...
invalid     # <- means server was down, NOT that assertions failed
```

When all errors are connection failures and all static tools pass (check_adl_no_asserts, check_port_name_uniqueness, check_assertion_events), treat the ADL as structurally VALID pending server restoration.

## Anti-pattern

Treating a server-unavailability INVALID as a genuine assertion failure and repeatedly modifying the ADL or assertions in response to a server-down condition. This wastes all 4 verification attempts without any real diagnostic signal.
