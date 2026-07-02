---
id: until-assertion-csp-anti-pattern
type: verification-pattern
scope: assertion-design
status: active
tags: [assertion, temporal-logic, CSP, liveness, until, anti-pattern]
confidence: 0.96
references: 40
skill_ref: .claude/skills/reusableskill-assertion-design/SKILL.md
---

## Context

When writing temporal-logic assertions for Wright# (CSP-based) ADL systems where components interact in recurring cycles: a component A fires after component B in each interaction cycle, and you want to express that A cannot proceed before B in a given cycle.

## Distilled Rule

Do NOT use `[] ((!A) U (B))` ("globally, A is blocked until B") for events that recur across interaction cycles. In a multi-cycle concurrent CSP system, after B fires and the interaction completes, the next cycle can have A fire before B fires again — which makes `[] ((!A) U (B))` globally false. Instead, use liveness: `[] (B -> <> A)` ("globally, whenever B fires, A eventually fires"), which correctly captures sequencing intent within each cycle without making impossible global demands.

## Example

**Incorrect assertion (fails verification):**
```
assert eshop |= [] ((!RiskDecision.evaluate.evaluated) U (FraudGateway.submitfraud.fraudsubmitted));
```
- Fails because after cycle 1 completes, in cycle 2 `evaluated` can fire before `fraudsubmitted`.

**Correct assertion (passes verification):**
```
assert eshop |= [] (FraudGateway.submitfraud.fraudsubmitted -> <> RiskDecision.evaluate.evaluated);
```
- Captures: whenever fraud is submitted, evaluation eventually follows.

## One-Shot Connector Context

When A and B each occur at most once (e.g. connected via CSConnector `sender` which goes to `Skip`, or CHAINConnector `forwarder` which goes to `Skip`), `U` without `[]` is valid and verifiable:

```
assert chromium |= (!ContentRenderer.cr_recv_nav.cr_nav_recv) U (ContentBrowser.cb_navigate.cb_navigated);
```

However, even in a one-shot context, `[] ((!A) U (B))` fails: after both A and B fire once and all connectors go to `Skip`, the system is in a "done" state where neither A nor B can ever fire again. From that state `(!A) U (B)` requires B to eventually happen, but it cannot — making `[]` globally false.

**Rule:** For one-shot ordering guarantees (each event fires at most once), use bare `U` without the outer `[]`:
```
assert sys |= (!A) U (B);   -- valid: checks from initial state only
```

## Anti-pattern

Using `[] ((!A) U (B))` when either:
1. A and B are events that recur in repeated interaction cycles — `[]` demands ordering holds across ALL global states, but recurring systems naturally produce states where A fires at the start of a new cycle before B fires in that new cycle.
2. A and B are one-shot events (connectors go to Skip) — after both fire and connectors are exhausted, no future state can satisfy `(!A) U (B)` because B can never fire again, making `[]` false from the terminal state.
