"""
check_port_name_uniqueness.py
Checks that every port name declared in any component is unique across ALL
components in the system (Rule 1: port names must be unique within each
component and across all components).

Usage:
  python3 check_port_name_uniqueness.py <adl_file_path>
Exit 0: all port names are globally unique.
Exit 1: one or more port name collisions detected.
"""

import sys
import re
from collections import defaultdict


def parse_component_ports(adl_text):
    """
    Returns a dict: { port_name -> [component_name, ...] }
    listing every component that declares each port name.
    """
    port_to_components = defaultdict(list)

    # Match component blocks (one level of nesting tolerated)
    comp_pattern = re.compile(
        r'\bcomponent\s+(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
        re.DOTALL
    )
    # Match port declarations inside a component block
    port_pattern = re.compile(
        r'\bport\s+(\w+)\s*\([^)]*\)',
        re.DOTALL
    )

    for comp_match in comp_pattern.finditer(adl_text):
        comp_name = comp_match.group(1)
        comp_body = comp_match.group(2)

        for port_match in port_pattern.finditer(comp_body):
            port_name = port_match.group(1)
            port_to_components[port_name].append(comp_name)

    return port_to_components


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_port_name_uniqueness.py <adl_file_path>")
        sys.exit(1)

    adl_path = sys.argv[1]
    try:
        with open(adl_path, 'r') as f:
            adl_text = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {adl_path}")
        sys.exit(1)

    port_to_components = parse_component_ports(adl_text)

    violations = []
    for port_name, components in sorted(port_to_components.items()):
        if len(components) > 1:
            violations.append(
                f"ERROR: Port name '{port_name}' is declared in multiple components: "
                f"{', '.join(components)}. Port names must be unique across all components (Rule 1)."
            )

    if violations:
        for v in violations:
            print(v)
        sys.exit(1)
    else:
        print("All port names are globally unique. No violations found.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Test suite (run with: python3 check_port_name_uniqueness.py --test)
# ---------------------------------------------------------------------------

TEST_CASES = [
    # (description, adl_text, expect_violations_containing)
    (
        "Clean ADL — all port names unique",
        """
        component Alpha {
          port send() = sent -> send();
          port receive() = received -> receive();
        }
        component Beta {
          port fetch() = fetched -> fetch();
          port store() = stored -> store();
        }
        """,
        []  # no violations expected
    ),
    (
        "Duplicate port name 'reminder' across two components",
        """
        component PassengerUI {
          port call() = callride -> call();
          port reminder() = passengerreminded -> reminder();
        }
        component DriverUI {
          port notify() = notified -> notify();
          port reminder() = driverreminded -> reminder();
        }
        """,
        ["'reminder'"]
    ),
    (
        "Duplicate port name 'logprematch' across two components",
        """
        component PreMatchEngine {
          port logprematch() = prematchlogged -> logprematch();
        }
        component AssignLog {
          port logassign() = logged -> logassign();
          port logprematch() = prematchrecorded -> logprematch();
        }
        """,
        ["'logprematch'"]
    ),
    (
        "Multiple duplicates",
        """
        component A {
          port foo() = e1 -> foo();
          port bar() = e2 -> bar();
        }
        component B {
          port foo() = e3 -> foo();
          port bar() = e4 -> bar();
          port baz() = e5 -> baz();
        }
        """,
        ["'bar'", "'foo'"]
    ),
    (
        "Intra-component duplicate (same port declared twice in one component)",
        """
        component A {
          port foo() = e1 -> foo();
          port foo() = e2 -> foo();
        }
        """,
        ["'foo'"]
    ),
]


def run_tests():
    import io
    import contextlib

    passed = 0
    failed = 0

    for desc, adl_text, expected_violations in TEST_CASES:
        port_to_components = parse_component_ports(adl_text)

        violations = []
        for port_name, components in sorted(port_to_components.items()):
            if len(components) > 1:
                violations.append(
                    f"ERROR: Port name '{port_name}' is declared in multiple components: "
                    f"{', '.join(components)}. Port names must be unique across all components (Rule 1)."
                )

        # Check expected violations
        ok = True
        if not expected_violations:
            if violations:
                print(f"FAIL [{desc}]: expected no violations, got: {violations}")
                ok = False
        else:
            for ev in expected_violations:
                if not any(ev in v for v in violations):
                    print(f"FAIL [{desc}]: expected violation containing '{ev}' not found. Got: {violations}")
                    ok = False

        if ok:
            print(f"PASS [{desc}]")
            passed += 1
        else:
            failed += 1

    print(f"\n{passed} passed, {failed} failed.")
    return failed == 0


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--test':
        success = run_tests()
        sys.exit(0 if success else 1)
    main()
