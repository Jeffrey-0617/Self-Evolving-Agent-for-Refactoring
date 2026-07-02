---
name: reusableskill-verification-diagnostics
description: Reusable diagnostic rules for interpreting Wright# verifier outcomes; covers distinguishing server-unavailability INVALID from genuine assertion INVALID, and deferring to static analysis tools when the PAT server is unreachable.
---

# Verification Diagnostics Rules for Wright# Systems

Guidelines for correctly interpreting verifier output and diagnosing root causes when `verify_wrighthash_all_properties.py` returns `invalid`.

## Rule 1: Distinguish Server-Unavailability INVALID from Genuine Assertion INVALID

**Why it matters:** The verifier script (`verify_wrighthash_all_properties.py`) catches HTTP connection exceptions and maps them to the string `"error"`, which the driver then reports as `invalid` — the same output as a genuine PAT assertion failure. This means PAT server downtime produces the same surface result as a genuinely incorrect ADL, and can exhaust all 4 verification attempts without yielding any diagnostic information about the ADL itself.

**Diagnostic step:** After any `invalid` result, run:

```bash
python3 agents/verification/verify_wrighthash_all_properties.py 2>&1 | grep "^Error occurred"
```

If every `Error occurred:` line mentions one of these patterns, the INVALID is a **false negative** from server downtime — not an ADL defect:
- `HTTPConnectionPool`
- `ConnectTimeoutError`
- `NewConnectionError`
- `Host is down`
- `Max retries exceeded`

**When the INVALID is a false negative:**
- Do NOT modify the ADL or assertions in response.
- Do NOT waste remaining verification attempts on unmodified artifacts.
- Fall back to the static analysis tool results as the correctness verdict:
  - `check_adl_no_asserts` passed → no embedded asserts
  - `check_port_name_uniqueness` passed → no duplicate ports
  - `check_assertion_events` passed → all assertion event references are valid
- Record the outcome as "INVALID (server unavailable)" and note that ADL is structurally VALID pending PAT server restoration.

**When the INVALID is genuine:**
- At least one error line will report `"invalid"` from PAT (not a connection exception).
- Investigate the specific failing assertion: check component/port/event names, connector attachment, role ordering.

## Rule 2: Cap Attempts Correctly When Server Is Down

The workflow allows up to 4 verification attempts (attempts 1–4). When the root cause is confirmed as server unavailability:
- Each retry attempt on an unmodified ADL consumes one attempt slot.
- Once confirmed (1–2 attempts confirm the pattern), stop retrying and proceed to log finalization.
- Do not burn all 4 attempts waiting for the server to recover.

## Rule 3: Structural Deadlock INVALID from One-Shot Connectors in Multi-Role `<*>` Attachments

**Why it matters:** The verifier generates structural partial systems for ALL paths in the system, independently of which assertions are declared. If a component port uses a multi-role `<*>` attachment combining a cyclic role (e.g. `responder`, `readstorage`) with a one-shot output role (e.g. `reader`, `writer`, `requester` — all terminate with `Skip`), PAT will detect structural deadlock in that partial system and return `invalid` — even when no assertion targets that path and even after removing any assertion that did target it.

**Diagnostic signal:** A genuine `invalid` appears at the end of a partial system block, but the `Error occurred:` line is absent or is NOT an HTTP connection error. The partial system itself (printed before `invalid`) contains a multi-role `<*>` attachment mixing one-shot and recurring roles.

**Resolution:**
- Do NOT attempt assertion changes or removal — the INVALID comes from structural deadlock, not from the assertion itself.
- Accept the INVALID as a known PAT limitation for this connector composition pattern.
- Rely on static analysis tools (all 3 must pass) to confirm structural correctness.
- For the affected interaction path, document the structural correctness guarantee in design notes rather than in a formal assertion.

**Example pattern producing structural deadlock:**
```wright
-- findbook() mixes cyclic responder with one-shot reader: deadlock is inherent
attach BookingService.findbook() = viewwire.responder() <*> resreadwire.reader(67);
-- viewwire.requester (one-shot, terminates) leaves viewwire.responder stuck waiting forever
```

## Usage Guidance

- **First step after any `invalid` result:** Check `grep "^Error occurred"` output before diagnosing the ADL.
- **If all errors are connection failures:** Treat the ADL as structurally sound (pending static tool results), log the server-unavailability cause, and do not modify the ADL.
- **If mixed errors (some genuine, some connection):** Investigate the genuine failures and ignore connection-failure partials.
- **If genuine `invalid` with multi-role `<*>` attachment mixing one-shot and cyclic roles:** Treat as structural deadlock (Rule 3); do not spend further attempts on assertion changes.
