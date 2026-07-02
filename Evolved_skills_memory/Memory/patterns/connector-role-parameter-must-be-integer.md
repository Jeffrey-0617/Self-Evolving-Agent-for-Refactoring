---
id: connector-role-parameter-must-be-integer
type: repair-pattern
scope: connector-role-attach
status: active
tags: connector, role-parameter, integer, PAT, attach, verification-failure, parse-error, syntax
confidence: 0.97
references: 2
tool_ref: .claude/tools/check_role_param_integers/check_role_param_integers.py
---

## Context

When writing `attach` statements for Wright# connectors that have parameterised output roles — such as `publisher(j)`, `requester(j)`, `writer(j)`, `extsupplier(j)`, `reader(j)` — the actual parameter value passed in each attach statement must be an **integer literal**. This applies to every connector type (PSConnector, CSConnector, WRConnector, QRConnector, IOConnector, etc.).

## Distilled Rule

**Connector role parameters in attach statements must be integer literals.**

Every parameterised role — e.g. `publisher(j)`, `requester(j)`, `writer(j)`, `reader(j)`, `extsupplier(j)` — requires an integer value when instantiated in an `attach` or port-body expression. Using a letter identifier (e.g. `b`, `v`, `mm`, `cr`, `a`, `o`, `h`, `i`, `t`) instead of an integer causes PAT to return "An error has occurred." for **all** partial systems, making verification entirely fail. The parameter integers must also be unique across all role instantiations in the system (reuse of the same integer in two different role instantiations is incorrect).

Choose unique integers (e.g. sequential values that do not conflict with any integer already used in the same ADL). Audit every existing attach statement to identify which integers are already claimed before assigning new ones.

## Example

**Correct (integer parameters):**
```wright
attach TamperGuard.tghash()           = txhashwire.publisher(54);
attach AuditChain.acbuyer()           = buyerauditwire.publisher(55);
attach TimestampAuthority.tscertbuyer() = buyertswire.requester(65);
attach IntegrityVerifier.ivcheck()    = ivverifywire.requester(53);
attach OrderTransactionBlockchain.ivread() = ivblockchainwire.reader(69);
```

**Incorrect (letter parameters — causes PAT error):**
```wright
attach TamperGuard.tghash()           = txhashwire.publisher(b);      -- WRONG
attach AuditChain.acbuyer()           = buyerauditwire.publisher(a);  -- WRONG
attach TimestampAuthority.tscertbuyer() = buyertswire.requester(t);   -- WRONG
attach IntegrityVerifier.ivcheck()    = ivverifywire.requester(i);    -- WRONG
```

## Anti-pattern

Using any non-integer value (letter, variable name, symbolic identifier) as a connector role parameter:
- `publisher(b)`, `requester(j_var)`, `writer(mm)`, `reader(cr)`, `extsupplier(v)`
- PAT returns "An error has occurred." for **every** partial system — not a specific error pointing to the attach statement. The error appears identical to a server-unavailability false-negative but is NOT (grep for `^Error occurred` to distinguish: server errors produce that prefix; integer-parameter errors do not).
- All 3 static analysis tools (check_adl_no_asserts, check_port_name_uniqueness, check_assertion_events) PASS despite this error — the fault is invisible to existing tools.
- Fix: replace every letter parameter with a unique integer not already used in the ADL.
