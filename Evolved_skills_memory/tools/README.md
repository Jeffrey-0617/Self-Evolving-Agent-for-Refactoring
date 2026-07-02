# Static Analysis Tools

Python scripts written by the agent to catch known error classes in Wright# ADL files before submitting to the PAT formal verifier. Each tool exits 0 on success and 1 on violations.

Run all tools in this order before every verification:
```bash
python3 .claude/tools/check_adl_no_asserts/check_adl_no_asserts.py tmp/refactored.adl
python3 .claude/tools/check_port_name_uniqueness/check_port_name_uniqueness.py tmp/refactored.adl
python3 .claude/tools/check_role_param_integers/check_role_param_integers.py tmp/refactored.adl
python3 .claude/tools/check_assertion_events/check_assertion_events.py tmp/refactored.adl
```

---

## `check_port_name_uniqueness`

**What it checks:** Every port name declared in any component must be globally unique across all components. A collision causes verification failures — often appearing as a misleading assertion error rather than a naming conflict.

**Linked skill:** [`check-port-name-uniqueness`](../skills/check-port-name-uniqueness/SKILL.md)

**Usage:**
```bash
python3 .claude/tools/check_port_name_uniqueness/check_port_name_uniqueness.py tmp/refactored.adl
python3 .claude/tools/check_port_name_uniqueness/check_port_name_uniqueness.py --test  # run self-tests
```

**Testcases** (embedded in the script as `TEST_CASES`):

| # | Description | Expected outcome |
|---|---|---|
| 1 | All port names unique across two components | PASS — no violations |
| 2 | Port name `reminder` declared in both `PassengerUI` and `DriverUI` | FAIL — duplicate `reminder` |
| 3 | Port name `logprematch` declared in both `PreMatchEngine` and `AssignLog` | FAIL — duplicate `logprematch` |
| 4 | Two ports (`foo`, `bar`) duplicated across components A and B | FAIL — both duplicates reported |
| 5 | Same port declared twice within a single component | FAIL — intra-component duplicate |

Example from testcase 2:
```wright
-- FAIL: 'reminder' appears in PassengerUI and DriverUI
component PassengerUI {
  port call()     = callride -> call();
  port reminder() = passengerreminded -> reminder();
}
component DriverUI {
  port notify()   = notified -> notify();
  port reminder() = driverreminded -> reminder();  -- DUPLICATE
}
-- ERROR: Port name 'reminder' is declared in multiple components: PassengerUI, DriverUI.
--        Port names must be unique across all components (Rule 1).
```

Example from testcase 3 (real bug pattern from rideshare run):
```wright
-- FAIL: 'logprematch' appears in PreMatchEngine and AssignLog
component PreMatchEngine {
  port logprematch() = prematchlogged -> logprematch();
}
component AssignLog {
  port logassign()   = logged -> logassign();
  port logprematch() = prematchrecorded -> logprematch();  -- DUPLICATE
}
-- Fix: use distinct names scoped to the component
component PreMatchEngine {
  port sendprematch() = prematchlogged -> sendprematch();
}
component AssignLog {
  port storeprematch() = prematchrecorded -> storeprematch();
}
```

---

## `check_assertion_events`

**What it checks:** Every `Component.port.event` reference inside `assert` statements must match a bare identifier declared in that component's port CSP expression.

**Linked skill:** [`check-assertion-events`](../skills/check-assertion-events/SKILL.md)

**Testcases** (`check_assertion_events/testcases/`):

| File | Expected outcome | What it tests |
|---|---|---|
| [`example1.adl`](check_assertion_events/testcases/example1.adl) | SUCCESS | Valid assertion — event name exactly matches port declaration |
| [`example2.adl`](check_assertion_events/testcases/example2.adl) | SUCCESS | Multiple assertions across multiple components, all valid |
| [`example3.adl`](check_assertion_events/testcases/example3.adl) | FAILURE | Port declares `process`, assertion uses `sent` (wrong name) |
| [`example4.adl`](check_assertion_events/testcases/example4.adl) | FAILURE | Port declares `fraudsubmitted`, assertion uses truncated `submitted` |

---

## `check_role_param_integers`

**What it checks:** Every parameterised connector role (`publisher`, `requester`, `writer`, `reader`, `extsupplier`, `querier`, `forwarder`) in `attach` statements must use an integer literal. Letter parameters cause PAT to fail on all partial systems.

**Linked skill:** [`check-role-param-integers`](../skills/check-role-param-integers/SKILL.md)

Built-in self-tests: `python3 .claude/tools/check_role_param_integers/check_role_param_integers.py --test`

---

## `check_adl_no_asserts`

**What it checks:** The ADL file must contain no `assert` statements. Assertions must live only in `tmp/assertions.md`. Embedded asserts cause PAT errors during partial-system verification.

**Linked skill:** [`check-adl-no-asserts`](../skills/check-adl-no-asserts/SKILL.md)
