---
id: mediator-bus-port-extension-topology
type: design-pattern
scope: attach-design
status: active
tags: [mediator, bus, IPC, port-extension, fan-through, receiver-forwarder, Rule6, decomposition, new-lane]
confidence: 0.87
references: 1
skill_ref: .claude/skills/reusableskill-connector-rules/SKILL.md
---

## Context

When decomposing a monolithic component into two specialized halves (e.g. renderer process and browser process) with an existing mediator/bus component (e.g. IPC) in between, two related design decisions arise:

1. A **shared platform port** (e.g. `recv_sandbox`) already serves one downstream consumer; after decomposition it must also forward to a new consumer in the split-off component.
2. The **mediator/bus** already carries N existing communication lanes (each with dedicated ports and attach statements); the decomposition requires M new lanes that must not touch any of the N existing attach statements.

## Distilled Rule

**Rule A — Receiver-then-forwarder extension on existing port (Rule 6 compliant):**
When an existing platform/infrastructure port must serve as BOTH an input receiver (receiving from one upstream connector) AND an output forwarder (forwarding to one or more downstream connectors), use a `<*>` multi-role attachment with the input role first and all output roles after — satisfying Rule 6. Do NOT split into a separate port unless the port's CSP semantics conflict.

```
-- Existing port that receives and now also forwards:
attach Platform.recv_sandbox() = upstream_connector.receiver() <*> downstream_connector.forwarder(N);
--                               ^^ input role (first)           ^^ output role (second)
```

**Rule B — New-port extension on mediator/bus:**
When a mediator/bus component (IPC, Gateway, Broker) must handle new communication lanes introduced by decomposition, add **new dedicated ports** to the mediator for each new lane — do NOT reuse or modify existing port attach statements. Each new port is isolated (one input role, one output role per lane) and wired with fresh connector instances. Existing ports and their attach statements remain unchanged.

```
-- Existing mediator ports (unchanged):
component IPC {
  port send_ipc() = ...;
  port recv_browser() = ...;
  port recv_renderer() = ...;
}
-- New ports for new lanes (added, not replacing):
component IPC {
  port ipc_tab_to_cr() = ...;   -- new lane: Browser→IPC→ContentRenderer
  port ipc_cr_to_cb() = ...;    -- new lane: ContentRenderer→IPC→ContentBrowser
}
```

## Example

**Splitting Content into ContentRenderer (CR) and ContentBrowser (CB) with IPC mediation:**

```wright
-- Rule A: Platform.recv_sandbox extended as receiver+forwarder
attach Platform.recv_sandbox() = suid_to_platform.receiver() <*> seccomp_to_cr.forwarder(201);
-- recv_sandbox receives from SuidSandboxClient (input first) and forwards to SeccompBpf (output second)

-- Rule B: IPC extended with new ports for CR↔CB lanes
component IPC {
  port recv_renderer() = delivered_renderer -> recv_renderer();  -- existing, unchanged
  port ipc_tab_to_cr() = tab_to_cr -> ipc_tab_to_cr();          -- new lane for tab-open path
  port ipc_cr_to_cb()  = cr_to_cb_ipc -> ipc_cr_to_cb();        -- new lane for input-forwarding
}
-- New connector instances pair with the new IPC ports:
declare cb_to_ipc_tab = CHAINConnector;
declare ipc_to_cr_render = CHAINConnector;
attach IPC.ipc_tab_to_cr() = cb_to_ipc_tab.handler() <*> ipc_to_cr_render.forwarder(302);
-- Existing attach for recv_renderer is untouched
```

## Anti-pattern

- **Reusing an existing mediator port for a new lane**: attaching a new output role to an existing IPC port that already has a fully specified CSP sequence risks attach conflicts and confuses the semantics of the existing lane.
- **Splitting a platform port unnecessarily**: if a port can handle both receiver and forwarder roles in Rule 6 order, there is no need to declare a second port — doing so wastes a port slot and risks Rule 1 naming collisions.
- **Mixing new and old attach statements for the same port**: always declare fresh connector instances for new lanes; never extend an existing connector instance to carry an additional unrelated lane.
