---
id: conditional-absence-assertion-unsupported
type: verification-pattern
scope: assertion-design
status: active
tags: [assertion, conditional-absence, syntax, verifier, skip, Type3, implication, liveness]
confidence: 0.87
references: 7
skill_ref: .claude/skills/reusableskill-assertion-design/SKILL.md
---

## Context

When writing safety properties for Wright# ADL verification, a "conditional absence" (Type 3) assertion attempts to state: "if event A fires, event B must NOT subsequently fire" — written as `-> !(...)` implication form. The verifier (`verify_wrighthash_all_properties.py`) does not recognise this syntax and silently skips (treats as unrecognised) any assertion containing `-> !(...)`.

## Distilled Rule

Do NOT use `-> !(...)` (conditional absence / negative implication) syntax in assertions. The verifier does not support this pattern and will silently skip the assertion without reporting an error — giving a false impression that the property was checked. Use only:
- **Type 1 (Liveness):** `[] (A -> <> B)` — whenever A fires, B eventually fires
- **Type 2 (Global absence):** `[] (!A)` — A never fires
- **Type 3 alternative (reframe as liveness):** If you need "A implies NOT B", consider reframing as a liveness property on the alternative path, or omit the assertion and document the invariant as a design constraint.

## Example

**Unsupported (silently skipped):**
```
assert system |= [] (SecureInject.inject_credential.credential_injected -> !(LibHistory.store_entry.entry_stored));
assert system |= [] (ErrorHandling.recv_error.error_received -> !(CredentialVault.retrieve_secret.secret_retrieved));
```
- The verifier logs these as "unrecognised syntax" and skips them; the overall result is still VALID but these properties are unchecked.

**Supported alternatives:**
```
-- Liveness: when credential injected, eventually vault retrieval completes (positive chain)
assert system |= [] (SecureInject.inject_credential.credential_injected -> <> CredentialVault.retrieve_secret.secret_retrieved);

-- Global absence if the event must truly never occur
assert system |= [] (!(LibHistory.store_entry.entry_stored));
```

## Anti-pattern

Writing conditional absence assertions as `[] (A -> !(B))` or `A -> !(...)` expecting them to enforce a safety property. The verifier silently skips these, producing a VALID result that does NOT actually verify the intended safety constraint. The missed assertions are reported only as "warnings" in the verifier output.
