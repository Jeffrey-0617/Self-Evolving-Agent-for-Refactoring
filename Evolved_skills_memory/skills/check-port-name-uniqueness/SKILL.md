---
name: check-port-name-uniqueness
description: Checks Wright# ADL for duplicate port names across components — verifies that every port name declared in any component is globally unique across all components (Rule 1 enforcement); invoke when verifying a refactored ADL.
---

# Check Port Name Uniqueness

Ensures that every port name in the ADL is unique across ALL components (Rule 1). A port name collision between two different components causes verification failure, often surfacing as a misleading assertion error rather than a naming conflict.

## Rule

Every port name declared in any component must be distinct from every other port name in every other component. Port names must be unique both within a component and across all components in the system.

## Usage

Run from the project root:
```bash
python3 .claude/tools/check_port_name_uniqueness/check_port_name_uniqueness.py <adl_file_path>
```
- Exit 0: all port names are globally unique
- Exit 1: one or more port name collisions detected

Run test suite:
```bash
python3 .claude/tools/check_port_name_uniqueness/check_port_name_uniqueness.py --test
```

## Failure Cases

### Failure 1: Same short name reused in two components (e.g. `reminder`)

**Incorrect ADL:**
```wright
component PassengerUI {
  port reminder() = passengerreminded -> reminder();
}
component DriverUI {
  port reminder() = driverreminded -> reminder();   -- DUPLICATE: violates Rule 1
}
```
**Error output:**
```
ERROR: Port name 'reminder' is declared in multiple components: PassengerUI, DriverUI. Port names must be unique across all components (Rule 1).
```
**Correct ADL:**
```wright
component PassengerUI {
  port passengerreminder() = passengerreminded -> passengerreminder();
}
component DriverUI {
  port driverreminder() = driverreminded -> driverreminder();
}
```
**Explanation:** Use component-scoped names to guarantee global uniqueness.

### Failure 2: Functionally symmetric components sharing a log port name

**Incorrect ADL:**
```wright
component PreMatchEngine {
  port logprematch() = prematchlogged -> logprematch();
}
component AssignLog {
  port logprematch() = prematchrecorded -> logprematch();  -- DUPLICATE: violates Rule 1
}
```
**Error output:**
```
ERROR: Port name 'logprematch' is declared in multiple components: PreMatchEngine, AssignLog. Port names must be unique across all components (Rule 1).
```
**Correct ADL:**
```wright
component PreMatchEngine {
  port sendprematch() = prematchlogged -> sendprematch();
}
component AssignLog {
  port storeprematch() = prematchrecorded -> storeprematch();
}
```

## Solution Patterns

### Problem: Short intuitive name collides with an existing component's port

**Wrong approach:** Naming new ports by function (e.g. `reminder`, `log`, `receive`) without checking existing port names in the full ADL.

**Correct approach:**
1. Before finalizing any new port names, grep all existing port names in the ADL.
2. For each new port, verify there is no collision.
3. If a collision exists, prefix the port name with the component name or a component-role descriptor (e.g. `passengerreminder`, `driverreminder`).
