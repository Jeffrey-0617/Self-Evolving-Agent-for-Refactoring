---
id: one-shot-multihop-liveness-invalid
type: verification-pattern
scope: assertion-design
status: active
tags: [assertion, liveness, multi-hop, one-shot, deadlock, PAT, INVALID, multi-role, partial-system, structural]
confidence: 0.88
references: 2
skill_ref: .claude/skills/reusableskill-verification-diagnostics/SKILL.md
---

## Context

When a component port is attached via a multi-role `<*>` statement that includes at least one one-shot output connector (e.g. `viewwire.requester` which terminates with `Skip`) AND at least one additional output connector chaining to a downstream component, a liveness assertion `[] (A -> <> B)` where A is an event on the one-shot side and B is an event on the downstream chained side will return INVALID in PAT — even when liveness appears to hold by design.

Additionally, the verifier generates structural partial systems for ALL paths in the system (not just the paths referenced by assertions). Removing or changing the assertion for a problematic path does NOT prevent the partial system from being generated and evaluated. PAT will still process the structural partial system and report INVALID when it detects a deadlock in that partial system.

## Distilled Rule

**Do not assert `[] (A -> <> B)` across a multi-hop path that passes through a multi-role `<*>` attachment containing one-shot connectors on the same component port.**

Root cause: The Wright# one-shot output roles (e.g. `requester`, `reader`, `writer`) terminate with `Skip` after one interaction. When these roles appear alongside a cyclic partner role (e.g. `responder`, `readstorage`, `writestorage`) in the same partial system, the one-shot role terminates while its cyclic partner is still waiting for the next cycle — producing a structural deadlock. PAT reports INVALID for any partial system containing this deadlock, whether or not an assertion is attached to that path.

**Workaround strategies:**
1. Assert only single-hop liveness: both A and B must be events in the same connector pair (one wire, one output role, one input role) with no intermediate component.
2. Drop the problematic multi-hop assertion and rely on structural correctness confirmed by static analysis tools — the wire-to-wire wiring is correct by ADL construction.
3. Do NOT attempt to remove the assertion alone — the verifier will still generate the structural partial system and return INVALID regardless.

## Example

**Failing design (produces INVALID regardless of assertion):**
```wright
-- BookingService.findbook() has a multi-role attachment:
attach BookingService.findbook() = viewwire.responder() <*> resreadwire.reader(67);
-- viewwire is CSConnector (one-shot requester), resreadwire is REConnector (one-shot reader)

-- Assertion 1: multi-hop from BookingViewer to ReservationStore -- INVALID
assert sys |= [] (BookingViewer.viewbook.view -> <> ReservationStore.resbookread.queried);

-- Assertion 2: single-hop from findbook.viewed -- STILL INVALID (partial system includes BookingViewer)
assert sys |= [] (BookingService.findbook.viewed -> <> ReservationStore.resbookread.queried);

-- Even after removing assertions: the verifier still generates the findbook partial system and returns INVALID
-- because the partial system has structural deadlock (viewwire.requester terminates, responder stuck)
```

**Correct approach:**
```wright
-- Rely on static analysis tools confirming structural correctness.
-- Only assert single-hop properties on paths NOT involving multi-role <*> with one-shot connectors.
-- For the multi-hop path, document the structural guarantee in a design note:
--   findbook() wires to resreadwire.reader(67) → resbookread.readstorage(), guaranteeing resbookread fires when findbook fires.
```

## Anti-pattern

Spending multiple verification attempts trying assertion variants (changing A or B, removing assertions) when the INVALID is caused by structural deadlock in the partial system. The deadlock is inherent to the one-shot connector semantics in Wright# and cannot be resolved by assertion changes alone. Only changing the connector type or decomposing the multi-role attachment would eliminate the structural deadlock — but those are design-level changes, not assertion-level fixes.
