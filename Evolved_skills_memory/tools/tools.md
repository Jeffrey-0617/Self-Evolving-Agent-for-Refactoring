# Static Analysis Tools

| tool_name | rule | skill | description |
|---|---|---|---|
| check_assertion_events | Assertion event name validity | check-assertion-events | Verifies every Component.port.event reference in assert statements exists as a declared event in the port's CSP expression. |
| check_port_name_uniqueness | Rule 1 — global port name uniqueness | check-port-name-uniqueness | Verifies that every port name declared in any component is globally unique across all components in the system. |
| check_adl_no_asserts | ADL file must not contain assert statements | check-adl-no-asserts | Verifies that tmp/refactored.adl contains no assert statements; asserts must be in tmp/assertions.md only to prevent PAT errors during partial-system verification. Run this FIRST before all other tools. |
