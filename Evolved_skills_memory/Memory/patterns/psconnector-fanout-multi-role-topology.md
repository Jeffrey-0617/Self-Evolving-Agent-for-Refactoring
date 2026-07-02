---
id: psconnector-fanout-multi-role-topology
type: design-pattern
scope: attach-design
status: active
tags: [PSConnector, fan-out, multi-role, topology, one-to-many, Rule6, mixed-connector]
confidence: 0.92
references: 15
skill_ref: .claude/skills/reusableskill-connector-rules/SKILL.md
---

## Context

When a component must receive data from one upstream connector and then push that data to two or more downstream consumers, a single port can handle the fan-out using Rule 6 multi-role attachment — provided exactly one input role appears first and all output roles follow. This applies across connector types: the output roles may be from different connector types (e.g., one CSConnector requester and one PSConnector publisher) in the same `<*>` attachment.

## Distilled Rule

A component acting as a relay or distributor (one input, N outputs) should declare a single port that attaches: first the upstream connector's input role, then each downstream connector's output role in sequence. Rule 6 requires exactly one input role (first position); all subsequent roles must be output roles. The output roles may belong to connectors of different types — CSConnector requesters, PSConnector publishers, and QRConnector queriers can all follow a single input role in one `<*>` block.

**Format:**
```wright
ComponentPort <*> upstreamwire.inputrole() <*> downstreamwire1.outputrole(x) <*> downstreamwire2.outputrole(y);
```

## Example

**PSConnector fan-out (same connector type):**
EventStream distributes an event to two consumers (SOSGateway and LifeCare):

```wright
component EventStream {
  port evtgateway() = connlinewire.writestorage() <*> sosstreaminwire.writer(evt) <*> carestreaminwire.writer(evt);
  -- connlinewire.writestorage() is the input role (first)
  -- sosstreaminwire.writer() and carestreaminwire.writer() are output roles (second, third)
}

EventStream.evtgateway() <*> connlinewire.writestorage() <*> sosstreaminwire.writer(evt) <*> carestreaminwire.writer(evt);
```

**Mixed-connector fan-through (different output connector types):**
AccessController enforce port receives from one CSConnector (as responder) and forwards to both a CSConnector requester (DataCompartmentalizer) and a PSConnector publisher (AuditLogger):

```wright
component AccessController {
  port acbuyerenforce() = buyeracwire.responder() <*> buyerdcwire.requester(d) <*> buyerauditwire.publisher(a);
  -- buyeracwire.responder() is the input role (first)
  -- buyerdcwire.requester() and buyerauditwire.publisher() are output roles (second, third)
}
```

## Anti-pattern

Declaring a separate port for each downstream consumer when a single fan-out port suffices — or placing the output roles before the input role (violates Rule 6 ordering). Also avoid assuming fan-out only works within a single connector type: output roles may freely mix connector types as long as ordering is preserved.
