---
name: check-assertion-events
description: Checks Wright# ADL for assertion event name mismatches — verifies every Component.port.event reference in assert statements exists as a declared event in the corresponding port's CSP expression; invoke when verifying a refactored ADL.
---

# Check Assertion Events

Ensures that every event token referenced in a `Component.port.event` pattern inside `assert` statements is actually declared as an event in the corresponding component's port definition.

## Rule

Every event reference `<Component>.<port>.<event>` in an assert statement must correspond to a bare identifier that appears in the CSP sequence of that component's port declaration (excluding connector.role(args) calls and structural keywords Skip, STOP, new, component, connector, system, attachments, assert, role, port).

## Usage

Run from the project root:
```bash
python3 .claude/tools/check_assertion_events/check_assertion_events.py <adl_file_path>
```
- Exit 0: all assertion event references are valid
- Exit 1: one or more event references are missing or the port/component does not exist

## Failure Cases

### Failure 1: Truncated event name
**Incorrect ADL:**
```wright
component FraudGateway {
  port submitfraud(j) = process -> fraudsubmitted -> sentwire.writer(j) -> Skip;
}
-- assertion:
assert fraud |= [] ((!RiskDecision.evaluate.evaluated) U (FraudGateway.submitfraud.submitted));
```
**Error output:**
```
ERROR: Assertion references FraudGateway.submitfraud.submitted but event 'submitted' is not declared in port 'submitfraud' of component 'FraudGateway'. Declared events: ['fraudsubmitted', 'process']
```
**Correct ADL:**
```wright
assert fraud |= [] ((!RiskDecision.evaluate.evaluated) U (FraudGateway.submitfraud.fraudsubmitted));
```
**Explanation:** The port declares `fraudsubmitted`, not `submitted`. The assertion must use the full event name verbatim.

### Failure 2: Completely wrong event name
**Incorrect ADL:**
```wright
component Alpha {
  port send(j) = process -> sentwire.writer(j) -> Skip;
}
-- assertion:
assert test |= [] (Alpha.send.sent -> <> Beta.receive.processed);
```
**Error output:**
```
ERROR: Assertion references Alpha.send.sent but event 'sent' is not declared in port 'send' of component 'Alpha'. Declared events: ['process']
```
**Correct ADL:**
```wright
assert test |= [] (Alpha.send.process -> <> Beta.receive.processed);
```
**Explanation:** The port `send` only exposes the `process` event. `sent` does not exist in its sequence.

### Failure 3: Tool run on assertions-only file (no component declarations)

**Symptom:** When assertions are stored in a separate file (e.g. `tmp/assertions.md`) and the tool is run on that file alone, it reports port-not-found errors for all references because it cannot find the component declarations.

**Error output (running on assertions.md alone):**
```
ERROR: Assertion references PassengerUI.schedule.ridescheduled but component 'PassengerUI' has no port named 'schedule'.
...
```
**Root cause:** The tool parses a single file for both component definitions and assert statements. If assertions are in a separate file, it sees no components and reports all references as missing.

**Correct approach:** Combine the ADL and assertions into a single file before running the tool:
```bash
cat tmp/refactored.adl tmp/assertions.md > /tmp/combined_check.adl
python3 .claude/tools/check_assertion_events/check_assertion_events.py /tmp/combined_check.adl
```
Or embed the assert statements directly in the ADL file before checking.

### Failure 4: Assertions written with bare event names (silent false pass)

**Symptom:** Tool exits 0 with "No assertion event references found. No violations detected." even though assertions are wrong.

**Cause:** Assertions were written using bare event names (e.g., `mi_format_adapt_req`) instead of the required `Component.port.event` format (e.g., `ModelImporter.mi_request_format_adapt.mi_format_adapt_req`). The tool finds no `Component.port.event` patterns to validate and reports a vacuous pass.

**Incorrect assertions.md:**
```
assert archstudio |= [] (mi_format_adapt_req -> <> far_adapt_req_handled);
```

**Correct assertions.md:**
```
assert archstudio |= [] (ModelImporter.mi_request_format_adapt.mi_format_adapt_req -> <> FormatAdapterRegistry.far_handle_adapt_req.far_adapt_req_handled);
```

**Detection:** If the tool output says "No assertion event references found" instead of "All assertion event references are valid", the assertions are not in `Component.port.event` format — rewrite them.

### Failure 5: Port name written with parentheses in assertion (silent false pass)

**Symptom:** Tool exits 0 with "No assertion event references found. No violations detected." even though assertions reference valid components and events.

**Cause:** Assertions were written as `Component.port().event` (with parentheses on the port name, mirroring ADL port declaration syntax) instead of the required `Component.port.event` format. The tool pattern-matches `Word.word.word`; `Word.word().word` does not match and produces a vacuous pass, identical to Failure 4.

**Incorrect assertions.md:**
```
assert chromium |= [] (Browser.open_tab().tab_opened -> <> ContentBrowser.cb_open_tab().cb_tab_opened);
```

**Correct assertions.md:**
```
assert chromium |= [] (Browser.open_tab.tab_opened -> <> ContentBrowser.cb_open_tab.cb_tab_opened);
```

**Detection:** Same as Failure 4 — if the tool output says "No assertion event references found" instead of "All assertion event references are valid", check whether port names in assertions have parentheses (`port()`) and remove them.

## Solution Patterns

### Problem: Event name does not match port declaration
**Wrong approach:**
```wright
assert sys |= [] (Foo.bar.baz -> <> ...);  -- 'baz' is an assumption, not checked
```
**Correct approach:**
1. Open the component's port definition in the ADL.
2. Read the CSP sequence after `=` and before `;`.
3. List every bare identifier (not part of `connector.role(args)` calls) — those are the valid event names.
4. Use one of those names exactly in the assertion.
5. Do NOT include parentheses on the port name: use `Component.port.event`, not `Component.port().event`.
