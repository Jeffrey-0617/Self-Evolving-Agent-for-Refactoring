"""
check_assertion_events.py
Checks that every event referenced in assert statements as
  <Component>.<port>.<event>
exists as a declared event token in the corresponding component's port definition.

Usage:
  python3 check_assertion_events.py <adl_file_path>
Exit 0: all assertion event references are valid.
Exit 1: one or more event references are missing or unresolvable.
"""

import sys
import re


def parse_port_events(adl_text):
    """
    Returns a dict: { (component_name, port_name) -> set(event_tokens) }

    Strategy: for each port's CSP expression, split on '->' to get segments.
    Each segment may be:
      - a bare identifier (event name): e.g. process, evaluated, fraudsubmitted
      - a connector.role(args) call: e.g. csconn.requester(j)
      - Skip, STOP (terminal keywords)
      - a recursive call matching the port name itself

    We collect all bare identifiers from each segment, excluding known structural
    keywords that are not event names (Skip, STOP, new, component, connector,
    system, attachments, assert, role, port) and excluding connector.role patterns.
    """
    port_events = {}

    # Structural keywords that are never event names
    structural_keywords = {
        'Skip', 'STOP', 'new', 'component', 'connector',
        'system', 'attachments', 'assert', 'role', 'port',
    }

    # Match component blocks (handles one level of nesting)
    comp_pattern = re.compile(
        r'\bcomponent\s+(\w+)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
        re.DOTALL
    )
    # Match port declarations inside a component block
    port_pattern = re.compile(
        r'\bport\s+(\w+)\s*\([^)]*\)\s*=\s*([^;]+);',
        re.DOTALL
    )

    for comp_match in comp_pattern.finditer(adl_text):
        comp_name = comp_match.group(1)
        comp_body = comp_match.group(2)

        for port_match in port_pattern.finditer(comp_body):
            port_name = port_match.group(1)
            port_expr = port_match.group(2)

            # Remove connector.role(...) patterns — these are not event names
            cleaned = re.sub(r'\w+\.\w+\s*\([^)]*\)', '', port_expr)
            # Remove multi-role attachment operator
            cleaned = cleaned.replace('<*>', ' ')
            # Split on '->' to get individual terms
            segments = re.split(r'\s*->\s*', cleaned)

            events = set()
            for seg in segments:
                seg = seg.strip()
                # Each segment is a bare identifier (possibly with parens for recursive call)
                # Remove parens: port_name() recursive call
                seg_bare = re.sub(r'\(\s*\)', '', seg).strip()
                # Collect all identifiers
                tokens = re.findall(r'\b([a-zA-Z_]\w*)\b', seg_bare)
                for t in tokens:
                    if t not in structural_keywords:
                        events.add(t)

            key = (comp_name, port_name)
            port_events[key] = events

    return port_events


def parse_assertions(adl_text):
    """
    Returns a list of (component, port, event) tuples found in assert statements.
    Matches patterns like: Component.portname.eventname
    """
    references = []
    # Find all assert statements
    assert_pattern = re.compile(r'\bassert\b[^;]+;', re.DOTALL)
    # Match Component.port.event (component starts uppercase)
    ref_pattern = re.compile(r'\b([A-Z]\w*)\s*\.\s*(\w+)\s*\.\s*(\w+)\b')

    for assert_match in assert_pattern.finditer(adl_text):
        assertion_text = assert_match.group(0)
        # Remove the preamble: "assert <system> |=" so system name is not mistaken for component
        body = re.sub(r'assert\s+\w+\s*\|=', '', assertion_text)
        for ref_match in ref_pattern.finditer(body):
            references.append((
                ref_match.group(1),
                ref_match.group(2),
                ref_match.group(3)
            ))

    return references


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_assertion_events.py <adl_file_path>")
        sys.exit(1)

    adl_path = sys.argv[1]
    try:
        with open(adl_path, 'r') as f:
            adl_text = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {adl_path}")
        sys.exit(1)

    port_events = parse_port_events(adl_text)
    references = parse_assertions(adl_text)

    if not references:
        print("No assertion event references found. No violations detected.")
        sys.exit(0)

    violations = []
    for (comp, port, event) in references:
        key = (comp, port)
        if key not in port_events:
            violations.append(
                f"ERROR: Assertion references {comp}.{port}.{event} "
                f"but component '{comp}' has no port named '{port}'."
            )
        elif event not in port_events[key]:
            declared = sorted(port_events[key]) or ['(none detected)']
            violations.append(
                f"ERROR: Assertion references {comp}.{port}.{event} "
                f"but event '{event}' is not declared in port '{port}' of component '{comp}'. "
                f"Declared events: {declared}"
            )

    if violations:
        for v in violations:
            print(v)
        sys.exit(1)
    else:
        print("All assertion event references are valid. No violations found.")
        sys.exit(0)


if __name__ == '__main__':
    main()
