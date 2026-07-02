"""
check_role_param_integers.py
Checks that every parameterised connector role in attach statements and port-body
expressions uses an INTEGER literal as its parameter value.

Wright# connector roles such as publisher(j), requester(j), writer(j), reader(j),
extsupplier(j), querier(j), forwarder(j) must be instantiated with integer literals
in attach statements and port bodies. Using a letter identifier (e.g. b, v, mm, cr)
causes PAT to return "An error has occurred." for all partial systems, making
verification entirely fail. This error is invisible to all other static tools.

Usage:
  python3 check_role_param_integers.py <adl_file_path>
Exit 0: all role parameters are integer literals (or parameterless).
Exit 1: one or more non-integer role parameters detected.
"""

import sys
import re


# Known output role names that require an integer parameter.
# Input roles (responder, writestorage, blockstorage, subscriber, receiver) take no parameter.
# This list covers all standard Wright# connector role names; extend as needed.
PARAMETERISED_ROLES = {
    'publisher', 'requester', 'writer', 'reader',
    'extsupplier', 'querier', 'forwarder', 'sender',
}


def find_non_integer_role_params(adl_text):
    """
    Scan all attach statements and port body expressions for role invocations of
    the form  rolename(value)  where value is NOT an integer literal.

    Returns a list of (line_number, line_text, role_name, bad_value) tuples.
    """
    violations = []

    # Pattern matches: rolename(something)
    # We capture the role name and whatever is inside the parens.
    role_call_pattern = re.compile(r'\b(\w+)\(([^)]*)\)')

    for lineno, line in enumerate(adl_text.splitlines(), start=1):
        # Skip comment lines (Wright# uses --)
        stripped = line.strip()
        if stripped.startswith('--'):
            continue
        # Strip inline comments before matching
        code_part = re.sub(r'--.*$', '', line)

        for m in role_call_pattern.finditer(code_part):
            role_name = m.group(1)
            param_value = m.group(2).strip()

            if role_name not in PARAMETERISED_ROLES:
                continue

            # Empty param is fine for parameterless roles — but PARAMETERISED_ROLES
            # should always have a value; flag empty too.
            if param_value == '':
                # No parameter — this is an input role being mistakenly listed,
                # or a genuinely parameterless invocation. Skip (not our concern).
                continue

            # Check: is the param an integer literal?
            if not re.fullmatch(r'-?\d+', param_value):
                violations.append((lineno, line.rstrip(), role_name, param_value))

    return violations


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_role_param_integers.py <adl_file_path>")
        sys.exit(1)

    adl_path = sys.argv[1]
    try:
        with open(adl_path, 'r') as f:
            adl_text = f.read()
    except FileNotFoundError:
        print(f"ERROR: File not found: {adl_path}")
        sys.exit(1)

    violations = find_non_integer_role_params(adl_text)

    if violations:
        for lineno, line_text, role_name, bad_value in violations:
            print(
                f"ERROR (line {lineno}): role '{role_name}' has non-integer parameter "
                f"'{bad_value}' — PAT requires integer literals for role parameters. "
                f"Replace '{bad_value}' with a unique integer."
            )
            print(f"  >> {line_text}")
        sys.exit(1)
    else:
        print("All connector role parameters are integer literals. No violations found.")
        sys.exit(0)


# ---------------------------------------------------------------------------
# Test suite (run with: python3 check_role_param_integers.py --test)
# ---------------------------------------------------------------------------

TEST_CASES = [
    (
        "Clean ADL — all role params are integers",
        """
        attach TamperGuard.tghash()    = txhashwire.publisher(54);
        attach AuditChain.acbuyer()    = buyerauditwire.publisher(55);
        attach IntegrityVerifier.ivcheck() = ivverifywire.requester(53);
        attach OrderTransactionBlockchain.tgappend() = tgblockchainwire.writestorage();
        attach OrderTransactionBlockchain.ivread()   = ivblockchainwire.reader(69);
        """,
        []  # no violations expected
    ),
    (
        "Letter param in publisher role",
        """
        attach TamperGuard.tghash() = txhashwire.publisher(b);
        """,
        [("publisher", "b")]
    ),
    (
        "Multiple letter params across different role types",
        """
        attach AuditChain.acmm()  = mmauditwire.publisher(mm);
        attach TS.tscert()        = buyertswire.requester(t);
        attach DB.store()         = storewire.writer(v);
        attach IntVer.ivcheck()   = ivwire.requester(i);
        """,
        [("publisher", "mm"), ("requester", "t"), ("writer", "v"), ("requester", "i")]
    ),
    (
        "Mix of valid integers and invalid letters",
        """
        attach Foo.p1() = wire1.publisher(42);
        attach Foo.p2() = wire2.publisher(x);
        attach Bar.p3() = wire3.requester(17);
        attach Bar.p4() = wire4.requester(cr);
        """,
        [("publisher", "x"), ("requester", "cr")]
    ),
    (
        "Input roles (no param) are not flagged",
        """
        attach OrdersDB.srv()  = orderwire.writestorage();
        attach Consumer.recv() = streamwire.blockstorage();
        attach Server.svc()    = reqwire.responder();
        attach Topic.sub()     = pubwire.subscriber();
        """,
        []
    ),
    (
        "Negative integers are valid",
        """
        attach Foo.p() = wire.publisher(-1);
        """,
        []
    ),
    (
        "Comments with letters are not flagged",
        """
        -- attach Foo.p() = wire.publisher(b);   this is a comment
        attach Foo.p() = wire.publisher(99);
        """,
        []
    ),
    (
        "extsupplier with letter param",
        """
        attach RealTimeOracle.push() = streamwire.extsupplier(j);
        """,
        [("extsupplier", "j")]
    ),
    (
        "reader with letter param",
        """
        attach DB.read() = readwire.reader(r);
        """,
        [("reader", "r")]
    ),
]


def run_tests():
    passed = 0
    failed = 0

    for desc, adl_text, expected in TEST_CASES:
        violations = find_non_integer_role_params(adl_text)
        # Build simplified results for comparison: list of (role, bad_value)
        got = [(v[2], v[3]) for v in violations]

        ok = True
        if not expected:
            if got:
                print(f"FAIL [{desc}]: expected no violations, got: {got}")
                ok = False
        else:
            for exp_role, exp_val in expected:
                if not any(r == exp_role and v == exp_val for r, v in got):
                    print(
                        f"FAIL [{desc}]: expected violation (role='{exp_role}', "
                        f"param='{exp_val}') not found. Got: {got}"
                    )
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
