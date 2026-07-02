---
id: assertion-event-name-mismatch
type: repair-pattern
scope: assertion-authoring
status: active
tags: [assertion, event-name, typo, verification-failure, naming, bare-event, silent-pass, format]
confidence: 0.94
references: 31
tool_ref: .claude/tools/check_assertion_events/check_assertion_events.py
---

## Context

When writing temporal-logic assertions referencing component port events in Wright# ADL, three related failure modes exist: (1) using a wrong or truncated event name in an otherwise correctly formatted `Component.port.event` reference; (2) omitting the `Component.port.` prefix entirely and writing bare event names, which causes `check_assertion_events` to report a vacuous pass ("No assertion event references found") rather than a validation error; (3) writing `Component.port().event` with parentheses on the port name — the tool cannot parse this as `Component.port.event` and reports the same vacuous pass as failure mode (2).

## Distilled Rule

Every assertion must use the full `Component.port.event` format — no parentheses on the port name. Before finalizing any assertion:
1. Confirm the assertion uses `<Component>.<port>.<event>` format — not bare event names alone, and not `<Component>.<port>().<event>` with parentheses on the port.
2. Verify that the event token exists verbatim in that component's port CSP sequence.

Use the `check_assertion_events` tool after combining the ADL and assertions into one file. If the output says **"No assertion event references found"** (rather than "All assertion event references are valid"), the assertions are not in `Component.port.event` format — rewrite them. This vacuous pass is triggered by BOTH bare event names AND `port()` parentheses in the reference.

## Example

**Incorrect assertion (truncated event name):**
```
assert eshop |= [] ((!RiskDecision.evaluate.evaluated) U (FraudGateway.submitfraud.submitted));
```
- `submitted` does not exist; the port declares event `fraudsubmitted`.

**Correct assertion:**
```
assert eshop |= [] ((!RiskDecision.evaluate.evaluated) U (FraudGateway.submitfraud.fraudsubmitted));
```

**Incorrect assertion (bare event name — silent false pass):**
```
assert archstudio |= [] (mi_format_adapt_req -> <> far_adapt_req_handled);
```
- The tool finds no `Component.port.event` patterns and reports "No assertion event references found" — a vacuous pass.

**Correct assertion:**
```
assert archstudio |= [] (ModelImporter.mi_request_format_adapt.mi_format_adapt_req -> <> FormatAdapterRegistry.far_handle_adapt_req.far_adapt_req_handled);
```

## Anti-pattern

- Guessing or abbreviating event names in otherwise correctly formatted assertions.
- Writing assertions with bare event names (skipping the `Component.port.` prefix), which causes `check_assertion_events` to silently pass without validating anything.
- Writing `Component.port().event` with parentheses on the port name — port declarations use `port name() = ...` syntax in ADL, but assertions must use `Component.port.event` without parentheses. The tool pattern-matches `Word.word.word`; `Word.word().word` does not match and triggers the same vacuous pass.

**Example of port-parentheses error (incorrect):**
```
assert chromium |= [] (Browser.open_tab().tab_opened -> <> ContentBrowser.cb_open_tab().cb_tab_opened);
```
**Correct:**
```
assert chromium |= [] (Browser.open_tab.tab_opened -> <> ContentBrowser.cb_open_tab.cb_tab_opened);
```
