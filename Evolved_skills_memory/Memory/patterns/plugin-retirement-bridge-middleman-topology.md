---
id: plugin-retirement-bridge-middleman-topology
type: design-pattern
scope: attach-design
status: active
tags: [plugin-retirement, technology-migration, bridge, middleman, CHAINConnector, forwarder, port-promotion, wire-replacement, component-retirement]
confidence: 0.87
references: 3
skill_ref: .claude/skills/reusableskill-connector-rules/SKILL.md
---

## Context

When a plugin or runtime subsystem (e.g. a native plugin, a legacy adapter) is retired and replaced by a new runtime, the old subsystem typically consisted of: (1) a plugin-entry component that acted as a CHAINConnector forwarder initiating the execution chain, (2) one or more pass-through or adapter components that forwarded execution to the old runtime, and (3) the old runtime itself receiving via a connector's input role. After retirement, these must be replaced without breaking existing wires that route into the old chain.

## Distilled Rule

When retiring a plugin/runtime subsystem and replacing it with a new runtime, apply three generalizable moves:

1. **Introduce a Bridge component as CHAINConnector forwarder**: the new Bridge replaces the old plugin-entry component's role as the initiator in the execution chain. The Bridge is a middleman: it receives from one upstream connector (input role) and forwards to the existing pass-through component via the same or a new CHAINConnector (output role in the same `<*>` port). Declare the Bridge's port as `receiver() <*> forwarder(n)`.

2. **Promote existing pass-through components to full middlemen**: an existing component that previously only had output roles (pure sender) may now also receive from the new Bridge. Add a new input port to the pass-through component so it receives the Bridge's forwarder signal; retain its existing output role toward the new runtime. This component becomes a genuine middleman (one input port, one or more output roles).

3. **Re-attach retired component's receiver slots to the new runtime**: any existing connector wires whose input role was attached to the retired component's port must be updated. Remove the retired component's attach statement and replace it with the new runtime component's port (same connector wire, new component). This avoids orphaned wires and satisfies Rule 4 (every connector role must be attached).

**Also apply:** port isolation (Rule 3) when the new runtime component receives from multiple connectors — declare one port per inbound connector.

## Example

```wright
-- Before (retired subsystem):
-- Content.call_plugin → content_to_ppapi (CSConnector) → Ppapi.ppapi_call()
-- Ppapi.ppapi_call() <*> content_to_ppapi.responder() <*> ppapi_to_nacl.forwarder(x)
-- Nonnacl.nonnacl_exec() = nonnacl_pipe.forwarder(y)  -- pure sender, no input
-- Nacl.exec_native() = remoting_to_media.receiver()   -- retired

-- After (replacement topology):
-- 1. Bridge replaces old plugin-entry forwarder:
declare content_to_wasm_bridge = CSConnector;
declare wasm_bridge_to_nonnacl = CHAINConnector;
component WasmAPIBridge {
  port bridge_wasm_api() = content_to_wasm_bridge.receiver()
      <*> wasm_bridge_to_nonnacl.forwarder(153);
}

-- 2. Existing pass-through promoted to middleman (Nonnacl now receives + forwards):
declare nonnacl_to_wasm = CHAINConnector;
component Nonnacl {
  port nonnacl_recv() = wasm_bridge_to_nonnacl.receiver();   -- new input port
  port nonnacl_fwd()  = nonnacl_to_wasm.forwarder(n);       -- existing output role, updated wire
}

-- 3. Re-attach retired component's slot to new runtime:
-- Before: attach Nacl.exec_native() = remoting_to_media.receiver()
-- After:
attach WasmRuntime.recv_remote_exec() = remoting_to_media.receiver();
-- (same wire: remoting_to_media; new component: WasmRuntime; retired: Nacl)

-- 4. New runtime: port isolation — one port per inbound connector:
component WasmRuntime {
  port load_wasm()             = nonnacl_to_wasm.receiver();          -- from Nonnacl
  port recv_wasm_msg()         = ipc_to_wasm.responder() <*> ...;    -- from IPC
  port recv_remote_exec()      = remoting_to_media.receiver();       -- from Remoting
  port exec_wasm_sandboxed()   = wasm_to_validator.requester(x)
      <*> wasm_to_v8.requester(y);                                   -- outbound fan-out
}
```

## Anti-pattern

- Reusing the retired component's connector wires without updating the attach statements — leaves the retired component's ports attached while the component is removed, causing Rule 4 failures (incomplete attachments).
- Merging the Bridge's input and forwarding roles onto an existing component that already has an input role — violates Rule 6 (at most one input role per `<*>` block) if that component receives from two connectors in the same port.
- Forgetting to promote the pass-through component to a middleman — results in the Bridge's forwarder role being unattached (no receiver), violating Rule 4.
- Placing all new runtime's input ports in a single `<*>` block when there are multiple inbound connectors — violates Rule 6; apply port isolation (one port per input role).
