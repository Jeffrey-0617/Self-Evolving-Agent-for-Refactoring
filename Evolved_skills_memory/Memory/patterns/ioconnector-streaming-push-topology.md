---
id: ioconnector-streaming-push-topology
type: design-pattern
scope: attach-design
status: active
tags: [IOConnector, streaming, push, recurring, extsupplier, blockstorage, continuous-feed, one-to-one, fan-through, mixed-output]
confidence: 0.93
references: 3
skill_ref: .claude/skills/reusableskill-connector-rules/SKILL.md
---

## Context

When a component must continuously push data to another component in a streaming or real-time feed topology (not a one-shot request/response), use IOConnector. This applies to: market data feeds, sensor streams, alert broadcasts, price feeds, camera/continuous-auth streams, and any recurring push where the supplier initiates repeatedly without waiting for a reply.

## Distilled Rule

Use **IOConnector** for continuous/recurring push connections:
- `extsupplier(j)` is the **output role**: fires `process` first, sends `token!j`, then recurs — it is attached to the data-producing component.
- `blockstorage()` is the **input role**: receives `token?j`, fires `process`, then recurs — it is attached to the data-consuming component.

Each IOConnector wire carries data in one direction, one-to-one. For a single source pushing to N consumers, declare N separate IOConnector wires (one per consumer), each with its own `extsupplier` and `blockstorage` role.

**Port isolation applies:** a consuming component that receives from multiple IOConnector wires must declare one separate port per `blockstorage()` input role (Rule 6 / port-isolation-for-dual-input-roles).

**Basic attach format (pure push, one-to-one):**
```wright
attach SourceComponent.sourceport() = somewire.extsupplier(n);
attach SinkComponent.sinkport()     = somewire.blockstorage();
```

**IOConnector fan-through variant:** A component that receives data via IOConnector (`blockstorage()`) and immediately fans out to multiple downstream connectors can combine the `blockstorage()` input role with multiple output roles in a single `<*>` statement. The `blockstorage()` input role must appear first (Rule 6). Output roles may be from any connector type (CSConnector requester, PSConnector publisher, WRConnector writer, etc.).

```wright
-- Component receives continuous stream AND fans out to N downstream connectors in one port:
attach StreamConsumer.sinkport() = streamwire.blockstorage()
    <*> downstreamwire1.requester(x)
    <*> downstreamwire2.publisher(y)
    <*> downstreamwire3.writer(z);
```

## Example

**Pure push (one source, multiple separate consumer wires):**

RealTimeOracle receives from MarketDataStream and pushes to three consumers using three separate IOConnector wires:

```wright
connector IOConnector {
  role blockstorage() = token?j -> process -> stored -> blockstorage();
  role extsupplier(j) = process -> token!j -> extsupplier(j);
}

component MarketDataStream {
  port mdsstream() = mdsstreamed -> mdsstream();         -- extsupplier output role
}
component RealTimeOracle {
  port rtosubscribe() = rtofeedprocessed -> rtosubscribe();  -- blockstorage input role (from MarketDataStream)
  port rtopricepush() = rtopricepushed -> rtopricepush();    -- extsupplier output role (to OrderTransaction)
  port rtoshipping()  = rtoshippingupdated -> rtoshipping();  -- extsupplier output role (to CarrierApp)
  port rtoalert()     = rtoalertsent -> rtoalert();           -- extsupplier output role (to AlertEngine)
}

declare marketstreamwire = IOConnector;
declare rtopricewire     = IOConnector;

attach MarketDataStream.mdsstream()   = marketstreamwire.extsupplier(11);
attach RealTimeOracle.rtosubscribe()  = marketstreamwire.blockstorage();
attach RealTimeOracle.rtopricepush()  = rtopricewire.extsupplier(22);
attach OrderTransaction.otprice()     = rtopricewire.blockstorage();
```

Note: RealTimeOracle has 4 separate ports — 1 blockstorage input port + 3 extsupplier output ports (one per consumer wire). This satisfies port isolation.

**IOConnector fan-through (blockstorage input + mixed output roles in one `<*>`):**

ContinuousAuth receives a camera stream via IOConnector and simultaneously fans out to multiple downstream services (biometric API, fraud alert, trip management, logging, payment freeze):

```wright
component ContinuousAuth {
  port camonitor() = camonitored -> camonitor();
}

attach DriverUI.castream()     = castreamwire.extsupplier(13);  -- IOConnector output role
attach ContinuousAuth.camonitor() =
    castreamwire.blockstorage()          -- IOConnector input role (first, Rule 6)
    <*> cabiometricwire.requester(65)    -- CSConnector output role
    <*> ftalertwire.publisher(66)        -- PSConnector output role
    <*> catripmgmtwire.publisher(67)     -- PSConnector output role
    <*> caloggingwire.writer(68)         -- WRConnector output role
    <*> capayfreezeswire.publisher(69);  -- PSConnector output role
```

ContinuousAuth uses a single port with 1 IOConnector input role + 5 mixed output roles — no port isolation needed because there is only one input role.

## Anti-pattern

- Using CSConnector for streaming push (CSConnector expects a reply from the responder; IOConnector has no reply channel and is appropriate for fire-and-forward semantics).
- Attempting to attach two `blockstorage()` input roles to the same port — violates Rule 6; declare a separate port per IOConnector input.
- Creating one IOConnector with multiple blockstorage roles to "fan-out" — IOConnector is one-to-one; use separate wires for each consumer.
- Placing output roles before the `blockstorage()` input role in a fan-through `<*>` statement — violates Rule 6 ordering.
