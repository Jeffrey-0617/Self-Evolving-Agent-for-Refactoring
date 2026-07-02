---
id: duplicate-port-name-across-components
type: repair-pattern
scope: port-naming
status: active
tags: [port, naming, Rule1, uniqueness, verification-failure, duplicate]
confidence: 0.92
references: 38
tool_ref: .claude/tools/check_port_name_uniqueness/check_port_name_uniqueness.py
---

## Context

When adding new components or ports to a Wright# ADL, port names must be globally unique across ALL components in the system (Rule 1). Reusing an intuitive short name (e.g. `reminder`, `logprematch`) in two different components causes the verifier to fail — the error may appear as an unrelated assertion failure rather than a naming conflict.

## Distilled Rule

Every port name declared in any component must be unique across the entire system. Before finalizing a component's ports, scan all existing port names in the ADL. If a new port name collides with any existing port name in any other component, rename it to a component-scoped unique name (e.g. prefix with the component name: `passengerreminder`, `driverreminder`, `sendprematch`, `storeprematch`).

## Example

**Incorrect (duplicate port names across components):**
```wright
component PassengerUI {
  port reminder() = passengerreminded -> reminder();   -- DUPLICATE
}
component DriverUI {
  port reminder() = driverreminded -> reminder();      -- DUPLICATE: violates Rule 1
}
component PreMatchEngine {
  port logprematch() = prematchlogged -> logprematch();  -- DUPLICATE
}
component AssignLog {
  port logprematch() = prematchrecorded -> logprematch(); -- DUPLICATE: violates Rule 1
}
```
- Causes verification failure when assertions reference these ports.

**Correct (component-scoped unique names):**
```wright
component PassengerUI {
  port passengerreminder() = passengerreminded -> passengerreminder();
}
component DriverUI {
  port driverreminder() = driverreminded -> driverreminder();
}
component PreMatchEngine {
  port sendprematch() = prematchlogged -> sendprematch();
}
component AssignLog {
  port storeprematch() = prematchrecorded -> storeprematch();
}
```

## Anti-pattern

Choosing short, functionally descriptive port names (e.g. `reminder`, `log`) without checking for collisions across other components. All existing ports in the entire system must be checked for uniqueness, not just within the current component being authored.
