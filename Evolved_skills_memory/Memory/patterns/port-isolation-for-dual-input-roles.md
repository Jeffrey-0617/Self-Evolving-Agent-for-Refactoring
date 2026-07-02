---
id: port-isolation-for-dual-input-roles
type: design-pattern
scope: attach-design
status: active
tags: [port, attach, input-role, Rule6, multi-role, isolation]
confidence: 0.90
references: 47
skill_ref: .claude/skills/reusableskill-connector-rules/SKILL.md
---

## Context

When a component needs to receive data from two or more different connectors (two different input roles) via `<*>` multi-role attachment (Rule 6), placing both input roles in a single port `<*>` block is invalid. Rule 6 allows at most one input role per `<*>` attachment. This also applies when a component has distinct functional responsibilities served by different connectors (e.g. data-forwarding vs. health-monitoring): declare a separate port for each connector the component is the input side of.

## Distilled Rule

When a component must act as the input side of two separate connectors, declare two separate ports — one port per input role. Never attach two input roles to the same port via a single `<*>` statement.

## Example

**Incorrect (two input roles in one port):**
```
component OrdersService {
  port receiveclearance() = riskorderwire.responder() <*> overridewire.responder() <*> ...
}
```
- Violates Rule 6: two input roles in one `<*>` block.

**Correct (two separate ports):**
```
component OrdersService {
  port receiveclearance()   = riskorderwire.responder() <*> ...;
  port receiveoverride()    = overridewire.responder() <*> ...;
}
```
- Each port handles one input role.

## Anti-pattern

Trying to "save" ports by collapsing multiple input-role connections into a single `<*>` multi-role attachment. This violates Rule 6 and must be split into separate ports.
