---
name: reusableskill-assertion-design
description: Reusable rules for writing correct temporal-logic assertions in Wright# (CSP-based) ADL systems; covers liveness vs. until-formula selection, event name verification, and concurrent cycle semantics.
---

# Assertion Design Rules for Wright# (CSP) Systems

Guidelines for writing correct temporal-logic (CTL/LTL-style) assertions in Wright# ADL, especially for concurrent, recurring interaction systems.

## Rule 1: Do Not Use `[] ((!A) U (B))` for Recurring Events

**Why it fails:** In a concurrent multi-cycle CSP system, `[] ((!A) U (B))` requires that in EVERY global state, A has not yet fired since the last time B fired. After a cycle completes and both A and B have fired, the next cycle's A can fire before the next B — making the formula globally false.

**Correct alternative:** Use liveness `[] (B -> <> A)`:
- Reads: "Globally, whenever B fires, A eventually fires."
- This correctly captures sequencing intent within each interaction cycle without imposing impossible cross-cycle global constraints.

**When `U` IS safe:** Only use bare `U` (without an outer `[]`) for strictly acyclic, bounded interaction sequences where A and B each occur at most once in the entire system run. The `[]` wrapper is unsafe even in one-shot contexts: after A and B each fire once and all connectors reach `Skip`, neither can fire again — from the terminal state, `(!A) U (B)` requires B to eventually happen but it cannot, making `[] ((!A) U (B))` false.

**One-shot correct form (no `[]`):**
```wright
-- Valid: checks from initial state only; A and B each fire at most once
assert sys |= (!A.port.event) U (B.port.event);
```

**Examples:**
```wright
-- WRONG: fails in recurring CSP systems
assert sys |= [] ((!RiskDecision.evaluate.evaluated) U (FraudGateway.submitfraud.fraudsubmitted));

-- CORRECT: use liveness
assert sys |= [] (FraudGateway.submitfraud.fraudsubmitted -> <> RiskDecision.evaluate.evaluated);
```

## Rule 2: Verify Event Names Against Port Declarations

Every event reference `<Component>.<port>.<event>` in an assertion must exactly match a bare identifier in the component's port CSP expression. Write port names WITHOUT parentheses: `Component.port.event`, never `Component.port().event`.

**Steps:**
1. Locate the port in the ADL: `port <portname>(...) = <CSP-expr>;`
2. Strip out any `connector.role(args)` sub-expressions — those are not events.
3. List all remaining bare identifiers in the `->` chain — those are the valid event names.
4. Use one of those exact tokens in the assertion.
5. Write `Component.port.event` — never include `()` on the port name in an assertion.

**Automated check:** Run `check_assertion_events` tool before submitting for formal verification:
```bash
python3 .claude/tools/check_assertion_events/check_assertion_events.py tmp/refactored.adl
```

If the output says **"No assertion event references found"** (rather than validation results), the assertions are either using bare event names or have `port()` parentheses — both trigger a vacuous pass.

**Example of mismatch (incorrect):**
```wright
-- port declares 'fraudsubmitted', assertion uses 'submitted'
assert sys |= [] (FraudGateway.submitfraud.submitted -> ...);  -- WRONG (truncated name)
-- parentheses on port name cause silent pass
assert sys |= [] (Browser.open_tab().tab_opened -> ...);       -- WRONG (port parentheses)
assert sys |= [] (FraudGateway.submitfraud.fraudsubmitted -> ...);  -- CORRECT
assert sys |= [] (Browser.open_tab.tab_opened -> ...);              -- CORRECT
```

## Rule 3: Choose the Right Assertion Type

| Intent | Correct form | Notes |
|---|---|---|
| A always eventually happens | `[] (<> A)` | Global liveness |
| After B, A eventually happens | `[] (B -> <> A)` | Conditional liveness |
| A and B never both true | `[] !(A /\ B)` | Safety / mutual exclusion |
| A is always true | `[] A` | Safety invariant |
| Bounded until (acyclic only) | `[] ((!A) U B)` | ONLY for one-shot, non-recurring events |

## Rule 4: Do NOT Use `-> !(...)` Conditional Absence Syntax

The verifier does NOT support conditional-absence assertions written as implication-to-negation form (`A -> !(B)`). These are silently skipped (reported as warnings), producing no verification result — they do NOT enforce the intended safety property.

**Unsupported — silently skipped:**
```wright
assert sys |= [] (SecureInject.inject_credential.credential_injected -> !(LibHistory.store_entry.entry_stored));
```

**Supported alternatives:**
- Reframe as liveness if a positive counterpart exists: `[] (A -> <> C)` where C is the expected positive outcome.
- Use global absence `[] (!B)` if B must truly never fire under any condition.
- If no supported form fits, document the constraint as a design note and omit the assertion (rather than writing a silently-skipped assertion).

## Rule 5: Do NOT Assert Multi-Hop Liveness Across `<*>` Attachments with One-Shot Connectors

**Why it fails:** When a component port uses a multi-role `<*>` attachment that mixes cyclic roles (e.g. `responder`, `readstorage`, `writestorage`) with one-shot output roles (e.g. `reader`, `writer`, `requester` — all terminate with `Skip`), PAT detects a structural deadlock in the generated partial system. This deadlock causes PAT to report `invalid` for ANY assertion targeting events in that partial system — whether the assertion is single-hop or multi-hop, and whether the assertion is present or absent.

**Key insight:** The verifier generates structural partial systems for ALL paths, independently of which assertions are declared. Removing an assertion for a problematic path does NOT prevent the partial system from being generated and evaluated as INVALID.

**Rule:** Do not write `[] (A -> <> B)` where A is an event on the one-shot side and B is an event on the downstream chained side of a multi-role `<*>` attachment that combines one-shot output roles with cyclic roles. Such assertions cannot be made to pass within Wright# connector constraints.

**Correct approach:**
- Limit assertions to single-hop paths on clean connector pairs (one wire, no `<*>` mixing).
- For multi-role `<*>` paths with one-shot + cyclic role mixing, accept that PAT will return INVALID and rely on static analysis tools for structural correctness confirmation.
- Document the structural guarantee as a design note rather than a formal assertion.

**Example (problematic — produces INVALID regardless of assertion changes):**
```wright
-- Multi-role attachment with one-shot reader + cyclic responder:
attach BookingService.findbook() = viewwire.responder() <*> resreadwire.reader(67);
-- Any assertion targeting events on this path will fail due to structural deadlock
assert sys |= [] (BookingViewer.viewbook.view -> <> ReservationStore.resbookread.queried);  -- INVALID
assert sys |= [] (BookingService.findbook.viewed -> <> ReservationStore.resbookread.queried);  -- STILL INVALID
-- Even removing the assertion: the partial system still returns INVALID
```

## Usage Guidance

- **Before asserting ordering between recurring events:** Ask "Do A and B both fire in repeated cycles?" If yes, do NOT use `U`. Use `-> <>` instead.
- **When writing a one-shot ordering assertion:** Use bare `U` without `[]`: `assert sys |= (!A) U (B);`. Do not wrap in `[]` — even one-shot connectors go to `Skip` and the terminal state cannot satisfy `(!A) U (B)` if B can no longer fire.
- **After writing assertions:** Run `check_assertion_events` to catch event name mismatches before formal verification. If it reports "No assertion event references found", check for bare event names OR port parentheses (`port()`) in assertions — both trigger a vacuous pass.
- **Assertion format:** Always use `Component.port.event` — never `Component.port().event`. Port names in ADL declarations have parentheses, but assertion references must not.
- **When a `U` assertion fails verification unexpectedly:** Check if the events recur. If they do, rewrite as liveness. If they are one-shot, remove the outer `[]`.
- **For conditional-absence (safety exclusion) properties:** Do not use `-> !(...)`. Use global absence or reframe as liveness. See Rule 4.
- **Before asserting liveness across multi-hop paths:** Check if any intermediate component port uses a multi-role `<*>` attachment mixing one-shot output roles with cyclic roles. If so, do NOT assert across that path — use static analysis tools instead. See Rule 5.
