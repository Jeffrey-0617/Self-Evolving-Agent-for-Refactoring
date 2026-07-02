---
name: reusableskill-connector-rules
description: Reusable design rules for Wright# connectors and multi-role port attachments; covers input/output role identification, Rule 6 attach ordering, and port isolation for components receiving from multiple connectors.
---

# Connector and Attach Design Rules for Wright#

Design guidance for declaring connectors and writing `<*>` multi-role port attachment statements correctly.

## Rule 1: Identify Input vs. Output Roles

In a connector definition:
- **Output role**: fires `process` first, then sends data via output channels (`ch!j`). It initiates the interaction.
- **Input role**: receives data via input channels (`ch?j`), then fires `process`. It responds to the initiator.

**Key heuristic:** Whichever role's `process` event fires first is the **output role** (the component attached to it executes first). The role that receives data before its `process` fires is the **input role**.

**CSConnector example:**
```wright
connector CSConnector {
  role requester(j) = process -> req!j -> res?j -> Skip;   -- OUTPUT role (process first)
  role responder()  = req?j -> invoke -> process -> res!j -> responder();  -- INPUT role (receives first)
}
```

**WRConnector example:**
```wright
connector WRConnector {
  role writer(j)      = process -> ch!j -> Skip;   -- OUTPUT role
  role writestorage() = ch?j -> process -> writestorage();  -- INPUT role
}
```

## Rule 2: Rule 6 — Multi-Role Attachment Ordering

In a `<*>` multi-role attachment statement, at most **one input role** is allowed, and it **must appear before** all output roles.

**Format:**
```wright
ComponentPort <*> connector.inputrole() <*> connector2.outputrole(n) <*> connector3.outputrole(m);
```

**Valid example (input role first):**
```wright
Payment.pay() <*> paywire.writestorage() <*> fraudpaymentwire.writer(99);
--              ^^ input role (first)     ^^ output role (second)
```

**Invalid (two input roles in one `<*>`):**
```wright
-- WRONG: two input roles
OrdersService.receive() <*> riskorderwire.responder() <*> overridewire.responder();
```

## Rule 3: Port Isolation for Multiple Input Roles

When a component must receive from two or more different connectors (as the input side of each), it CANNOT use a single port with two input roles in one `<*>` statement. Declare **separate ports** — one per input role.

**Wrong:**
```wright
component OrdersService {
  port receive() = riskorderwire.responder() <*> overridewire.responder() <*> ...;
  -- ERROR: two input roles in one <*>
}
```

**Correct:**
```wright
component OrdersService {
  port receiveclearance() = riskorderwire.responder() <*> ...;
  port receiveoverride()  = overridewire.responder() <*> ...;
}
```

**Rule of thumb:** Count the number of connectors for which this component is the input side. That is the minimum number of ports you need.

## Rule 4: Every Port Must Be Attached

Every declared port must appear in an attach statement. Unattached ports cause verification failures (incomplete attachment, violates Rule 4).

## Rule 5: Fan-Out / Fan-Through Topology (One Input, N Outputs)

When a component relays or distributes data — receiving from one upstream connector and pushing to two or more downstream connectors — a single port handles the fan-out. Declare the upstream connector's input role first, then all downstream output roles in the same `<*>` statement. The output roles may span different connector types (CSConnector requester, PSConnector publisher, QRConnector querier, etc.).

**Format:**
```wright
Component.port() <*> upstreamwire.inputrole() <*> downstreamwire1.outputrole(x) <*> downstreamwire2.outputrole(y);
```

**Valid example — same connector type fan-out (relay distributes to 2 PSConnector consumers):**
```wright
component EventStream {
  port evtgateway() = connlinewire.writestorage() <*> sosstreaminwire.writer(evt) <*> carestreaminwire.writer(evt);
}
EventStream.evtgateway() <*> connlinewire.writestorage() <*> sosstreaminwire.writer(evt) <*> carestreaminwire.writer(evt);
-- connlinewire.writestorage() is the input role (first); the writer roles are output roles.
```

**Valid example — mixed connector type fan-through (CSConnector input, CSConnector + PSConnector outputs):**
```wright
component AccessController {
  port acbuyerenforce() = buyeracwire.responder() <*> buyerdcwire.requester(d) <*> buyerauditwire.publisher(a);
  -- buyeracwire.responder() is the input role (CSConnector, first)
  -- buyerdcwire.requester() is a CSConnector output role (second)
  -- buyerauditwire.publisher() is a PSConnector output role (third)
}
```

**Rule of thumb:** Count the number of output consumers. Each gets one output role in the same `<*>` block. The single input role always comes first. Output roles may be from any connector type.

## Rule 6: Backend Decomposition Topology

When splitting one backend component into N specialized backends, choose a routing strategy and apply port isolation:

**Routing strategy A — Point-to-point CSConnector per caller** (most common for library/service splits where each caller needs only one sub-backend):
- Each caller gains one new `call_<sub>` port and one CSConnector wire to the specific sub-backend it needs.
- No fan-out port required; each caller routes directly.
- Analyse each caller's functional domain to determine routing; some callers may gain new connections not present before the split.

**Routing strategy B — Fan-out from a routing frontend** (for gateway/frontend components dispatching to all sub-backends):
- The routing component's port gains one new output role per new backend; use a single `<*>` fan-out attachment.

**Routing strategy C — Storage-tier decomposition (hot/cold + lifecycle coordinator)**:
When a data store is split into hot-storage (active/recent), cold-storage (archived/historical), and a coordinator (lifecycle/migration manager):
- Each caller that reads or writes both stores must be extended with a new output port per store it touches; use point-to-point CSConnector wires (Variant A topology per store).
- The coordinator connects to both stores via its own dedicated wires (one to hot-store for read-and-promote, one to cold-store for write-archive).
- Services with dual-store reads must declare two separate output roles — one targeting each store — and apply port isolation on each store's inbound port (Rule 3).
- Count wires precisely: each caller-store interaction requires its own wire. Under-counting wires is the most common mistake.

**Routing strategy D — Utility-split (cross-cutting service decomposed into N domain utilities)**:
When a shared cross-cutting utility component is decomposed into N domain-specific utilities (each serving a distinct functional domain):
- Apply Variant A (point-to-point CSConnector per caller) for all domain callers — each caller routes to exactly one domain utility.
- **Classify all callers by domain affinity**: the task spec may not list every caller; analyse each caller's functional role to assign it to the correct domain utility.
- **Expand shared infrastructure providers N-fold**: any component that previously had one port to the monolithic utility (e.g. a preferences/config provider, a shared resource store) must now expose N separate ports — one per new domain utility — because each utility is a distinct input role. Declare N new wires from the provider to each utility.
- **Use component-scoped port name prefixes on new utilities**: when N new utility components each declare similar serve ports (e.g. `srv_em`, `srv_archlight`), global uniqueness violations (Rule 1) are near-certain without prefixing. Always prefix ports with the component name (e.g. `editorutils_srv_em`, `analysisutils_srv_archlight`).

**Common rules for all strategies:**
1. **Port isolation on new backends**: each new backend declares one separate port per inbound upstream connector (it is the input side of each); apply Rule 3 above. Use `<sub>_srv_<caller>` naming.
2. **Analytics aggregator fan-out from existing services** (when applicable): existing services that now also feed an analytics backend extend their existing port using Rule 6 fan-out — add the new output role after the existing input role in the same `<*>` block.
3. **Wire reuse on role inheritance**: when a decomposed component's successor plays the identical role in an existing wire, reuse that wire — update only the component reference in the attach statement; do not create a new wire. **Wire-reuse exception**: do NOT reuse a connector wire when it already carries multi-role mixed attachments (other components attached as readers/pollers via mixed output roles on the same connector instance) and the new consumer only needs a single output role — declare a fresh connector instance instead to avoid inheriting unsafe multi-role mixing.

**Example — Point-to-point per caller (Variant A):**
```wright
declare cor_to_tpm = CSConnector;  -- GroupCore → ThirdPartyMath
attach GroupCore.cor_call_tpm() = cor_to_tpm.requester(16);
attach ThirdPartyMath.tpm_srv_cor() = cor_to_tpm.responder();
-- each caller-sub-backend pair gets its own wire and attach pair
```

**Example — Frontend fan-out to two new backends (Variant B):**
```wright
ShopFrontend.shop() <*> shopopswire.requester(o) <*> shopanalyticwire.requester(a);
-- one output role per new backend in the same <*> block
```

**Example — Analytics aggregator with N isolated input ports:**
```wright
component AnalyticsBackend {
  port analyticsrpt()      = shopanalyticwire.responder() <*> ...;  -- from frontend
  port analyticsorderevt() = ordereventwire.subscriber() <*> ...;   -- from OrdersService
  port analyticspaydata()  = payanalyticwire.subscriber() <*> ...;  -- from Payment
  port analyticsshipdata() = shipanalyticwire.subscriber() <*> ...;  -- from ShippingService
}
-- four separate ports: one per inbound connector (Rule 3 port isolation)
```

**Example — Extending an existing service to fan out to analytics:**
```wright
-- Before: Payment.pay() <*> paywire.writestorage()
-- After:
Payment.pay() <*> paywire.writestorage() <*> payanalyticwire.publisher(102);
--              ^^ input role (first)     ^^ new analytics output role (second)
```

**Example — Utility-split decomposition (Variant D): split one cross-cutting utility into N domain utilities:**
```wright
-- ArchStudioUtils split into EditorUtils, AnalysisUtils, ModelUtils, ViewUtils
-- Each caller assigned by domain affinity (spec-specified + inferred):
--   EditorUtils: EditorManager, ArchEdit, SharedEditorInfrastructure, Launcher, FileManager
--   AnalysisUtils: Archlight, TypeWrangler, GuardTracker, Schematron, SelectorDriver
--   ModelUtils: XArchADT, XArchChangeSet, ChangeSetUtils, CSRM, Meta
--   ViewUtils: Archipelago, GraphLayout, RationaleView, TracelinkView

-- Point-to-point per caller (Variant A applied per domain):
declare em_to_edutil = CSConnector;
attach EditorManager.em_to_edutil_port()   = em_to_edutil.requester(j);
attach EditorUtils.editorutils_srv_em()    = em_to_edutil.responder();  -- component-scoped prefix

-- Shared config provider expands 1 port → 4 ports (one per utility):
component PreferencesADT {
  port padt_to_editorutils()   = padt_to_edutil.responder()  <*> ...;
  port padt_to_analysisutils() = padt_to_anutil.responder()  <*> ...;
  port padt_to_modelutils()    = padt_to_modutil.responder() <*> ...;
  port padt_to_viewutils()     = padt_to_viewutil.responder()<*> ...;
}
-- 4 new wires: padt_to_edutil, padt_to_anutil, padt_to_modutil, padt_to_viewutil

-- Shared resource store similarly expands (1 port → 4):
component Resources {
  port editorutils_res()   = edutil_to_res.responder()  <*> ...;
  port analysisutils_res() = anutil_to_res.responder()  <*> ...;
  port modelutils_res()    = modutil_to_res.responder() <*> ...;
  port viewutils_res()     = viewutil_to_res.responder()<*> ...;
}
```

**Anti-patterns (Variant D):**
- Forgetting to expand shared providers — a single port from PreferencesADT to the old monolithic utility cannot serve all 4 new utilities simultaneously; each utility is an independent input role.
- Naming new utility ports without component-scope prefix (e.g. `srv_em` in both EditorUtils and AnalysisUtils causes Rule 1 violation).
- Failing to classify non-spec callers — every caller of the original utility must be assigned to a domain utility; omitting any caller leaves a dangling wire.

**Example — Storage-tier decomposition (Variant C): split one DB into hot + cold + coordinator:**
```wright
-- 12 new wires: one per caller-store pair; one per coordinator-store pair
declare fe_to_actdb     = CSConnector;   -- ShopFrontend reads active
declare pay_to_arch     = CSConnector;   -- Payment reads archive
declare olm_to_actdb    = CSConnector;   -- OrderLifecycleManager reads active
declare olm_to_arch     = CSConnector;   -- OrderLifecycleManager writes archive

-- Hot store: one inbound port per caller (port isolation, Rule 3)
component ActiveOrdersDB {
  port actdb_write()    = fe_write_wire.responder()  <*> ...;
  port actdb_frontend() = fe_to_actdb.responder()    <*> ...;
  port actdb_payment()  = pay_to_actdb.responder()   <*> ...;
  port actdb_lifecycle()= olm_to_actdb.responder()   <*> ...;
  -- ... one port per inbound caller
}
-- Coordinator connects to both stores:
attach OrderLifecycleManager.lifecycle_readactive()   = olm_to_actdb.requester(r);
attach OrderLifecycleManager.lifecycle_writearchive() = olm_to_arch.requester(w);
-- Service with dual-store reads gets two separate output ports:
attach OrdersService.get_active()  = ord_to_actdb.requester(a);   -- reads hot store
attach OrdersService.get_archive() = ord_to_arch.requester(b);    -- reads cold store
```

## Rule 7: IOConnector — Continuous Push / Streaming Topology

Use **IOConnector** when a component must continuously push data to another component with no reply (streaming, real-time feed, recurring push). IOConnector roles:
- `extsupplier(j)` — **output role**: fires `process` first, sends `token!j`, then recurs. Attach to the data-producing component.
- `blockstorage()` — **input role**: receives `token?j`, fires `process`, then recurs. Attach to the data-consuming component.

Each IOConnector wire is one-to-one. For one source pushing to N consumers, declare N separate wires. Port isolation (Rule 3) applies: a component receiving from multiple IOConnector wires must declare one port per `blockstorage()` input role.

**Basic attach format (pure push, one-to-one):**
```wright
declare streamwire = IOConnector;
attach Producer.sourceport() = streamwire.extsupplier(n);
attach Consumer.sinkport()   = streamwire.blockstorage();
```

**Example — one source, three consumers (three separate wires):**
```wright
attach RealTimeOracle.rtopricepush() = rtopricewire.extsupplier(22);
attach OrderTransaction.otprice()    = rtopricewire.blockstorage();

attach RealTimeOracle.rtoshipping()  = rtoshippingwire.extsupplier(33);
attach CarrierApp.crshipping()       = rtoshippingwire.blockstorage();

attach RealTimeOracle.rtoalert()     = rtoalertwire.extsupplier(44);
attach AlertEngine.aertosubscribe()  = rtoalertwire.blockstorage();
```

**IOConnector fan-through variant:** A component that receives a continuous stream via IOConnector (`blockstorage()`) and simultaneously fans out to multiple downstream connectors can combine the input role with output roles in a single `<*>` statement. The `blockstorage()` input role must appear first (Rule 6). Output roles may be from any connector type (CSConnector requester, PSConnector publisher, WRConnector writer, etc.). No extra port isolation is needed when there is only one input role.

```wright
-- Component receives continuous stream AND fans out to N downstream connectors in one port:
attach StreamConsumer.sinkport() = streamwire.blockstorage()
    <*> downstreamwire1.requester(x)    -- CSConnector output role
    <*> downstreamwire2.publisher(y)    -- PSConnector output role
    <*> downstreamwire3.writer(z);      -- WRConnector output role
```

**Example — IOConnector fan-through (stream-in, multi-connector fan-out):**
```wright
-- ContinuousAuth receives camera stream and triggers 5 downstream services:
attach DriverUI.castream()        = castreamwire.extsupplier(13);
attach ContinuousAuth.camonitor() = castreamwire.blockstorage()    -- input role (first)
    <*> cabiometricwire.requester(65)   -- CSConnector output
    <*> ftalertwire.publisher(66)       -- PSConnector output
    <*> catripmgmtwire.publisher(67)    -- PSConnector output
    <*> caloggingwire.writer(68)        -- WRConnector output
    <*> capayfreezeswire.publisher(69); -- PSConnector output
```

**Anti-patterns:**
- Using CSConnector for streaming (CSConnector requires a reply; IOConnector has no reply channel).
- Attaching two `blockstorage()` input roles to one port (violates Rule 6 / port isolation).
- Assuming IOConnector supports fan-out via multiple blockstorage roles — it does not; use one wire per consumer.
- Placing output roles before `blockstorage()` in a fan-through `<*>` statement (violates Rule 6 ordering).

## Rule 8: API Gateway / Frontend Architecture Migration Topology

When migrating a frontend from server-rendered (direct backend connections) to API-driven (all traffic routed via an APIGateway):

1. **Remove all direct frontend-to-service wires**: replace every direct frontend CSConnector wire with a wire from the frontend to the APIGateway. The frontend gains one port per entry point (all output roles — the frontend is always the requester/initiator).
2. **APIGateway as routing hub**: one input port per inbound frontend path (port isolation, Rule 3 above). Each APIGateway port fans out to the BFF or a specific backend via output roles in the same `<*>` block.
3. **BFF aggregator for composite backend calls**: one input port per inbound APIGateway connector (port isolation); one output role per downstream backend in a `<*>` fan-out.
4. **Existing backend services: add component-scoped ports for the new API path**: when a service's old port was connected only via the now-removed direct wire, rename or add a new port with a component-scoped name (e.g. `ordersservice_api`, `payment_api`). Remove or update the old port if it becomes unattached.
5. **CDN integration via custom connector**: for CDN-served assets, declare a custom CDNConnector with an output role (e.g. `cdnclient`, process first) attached to the frontend and an input role (e.g. `cdnserver`) attached to the CDNIntegration component.
6. **Port naming**: all new ports must be component-scoped (component-name prefix) to satisfy global uniqueness (Rule 1).
7. **Wire accounting**: explicitly list removed wires and added wires; expect net wire increase overall and net reduction on direct frontend-to-backend paths.

**Example — replacing direct frontend wires with gateway routing:**
```wright
-- Removed: catelequewire, userwire, cartwire, orderwire (direct ShopFrontend→service)

-- New wires routing through APIGateway:
declare frontend_browse_wire      = CSConnector;  -- ShopFrontend → APIGateway
declare apigateway_bff_browse_wire = CSConnector; -- APIGateway → BFFService
declare cdn_wire                  = CDNConnector; -- ShopFrontend → CDNIntegration

-- ShopFrontend: one output port per entry point
attach ShopFrontend.frontend_browse() = frontend_browse_wire.requester(b);
attach ShopFrontend.frontend_cdn()    = cdn_wire.cdnclient(a);

-- APIGateway: one input port per inbound path (port isolation); fans out via output role
component APIGateway {
  port apigateway_browse() = frontend_browse_wire.responder()          -- input role first
      <*> apigateway_bff_browse_wire.requester(x);                     -- output role
  port apigateway_login()  = frontend_login_wire.responder()
      <*> bff_auth_wire.requester(y);
}

-- BFFService: input from APIGateway, fans out to backends
component BFFService {
  port bff_browse() = apigateway_bff_browse_wire.responder()           -- input role first
      <*> bff_catalogue_wire.requester(c)                              -- output roles
      <*> bff_carts_wire.requester(d);
}

-- Existing service gains new component-scoped port (old 'postorder' removed):
attach OrdersService.ordersservice_api() = bff_orders_wire.responder() <*> ...;

-- CDN custom connector:
attach CDNIntegration.cdn_serve() = cdn_wire.cdnserver();             -- input role
```

**Anti-patterns:**
- Keeping old direct frontend-to-service wires alongside new gateway wires (orphaned or double-attached ports).
- Putting all frontend entry points on one APIGateway port (violates Rule 3: multiple input roles).
- Forgetting to update existing backend ports — unattached ports violate Rule 4.
- Using CSConnector for CDN delivery (no reply channel semantics; use a custom connector).

## Rule 9: Plugin / Technology Retirement with Bridge-Middleman Promotion

When retiring a plugin or runtime subsystem and replacing it with a new runtime, apply three moves:

1. **Introduce a Bridge component as CHAINConnector forwarder**: the Bridge replaces the old plugin-entry component's role as initiator. It is a middleman: receives from one upstream connector (input role) and forwards via CHAINConnector (output role) in the same `<*>` port — `receiver() <*> forwarder(n)`.

2. **Promote existing pass-through components to full middlemen**: an existing component that was previously a pure sender (output-only) gains a new input port to receive from the Bridge's forwarder. It keeps its existing output role toward the new runtime. Declare the new input port separately (port isolation) to avoid violating Rule 6.

3. **Re-attach retired component's receiver slots to the new runtime**: connector wires whose input role was attached to a now-retired component's port must be updated — replace the retired component with the new runtime in the attach statement. Same wire; new component.

**Always apply port isolation (Rule 3) on the new runtime** when it receives from multiple inbound connectors — one port per input role.

**Example:**
```wright
-- Bridge replaces old plugin forwarder:
component WasmAPIBridge {
  port bridge_wasm_api() = content_to_wasm_bridge.receiver()
      <*> wasm_bridge_to_nonnacl.forwarder(153);
}

-- Promoted middleman (was pure sender; now receives + forwards):
component Nonnacl {
  port nonnacl_recv() = wasm_bridge_to_nonnacl.receiver();  -- new input port
  port nonnacl_fwd()  = nonnacl_to_wasm.forwarder(n);      -- existing output (updated wire)
}

-- Re-attach retired component's slot to new runtime (same wire, new component):
-- Before: attach Nacl.exec_native() = remoting_to_media.receiver()
attach WasmRuntime.recv_remote_exec() = remoting_to_media.receiver();

-- New runtime: port isolation — one port per inbound connector:
component WasmRuntime {
  port load_wasm()        = nonnacl_to_wasm.receiver();
  port recv_wasm_msg()    = ipc_to_wasm.responder() <*> ...;
  port recv_remote_exec() = remoting_to_media.receiver();
  -- each inbound connector gets its own port
}
```

**Anti-patterns:**
- Leaving retired component's ports in attach statements — unattached roles violate Rule 4.
- Merging the Bridge's input role onto an existing component that already has an input role in the same `<*>` block — violates Rule 6.
- Omitting the promoted middleman's new input port — leaves the Bridge's forwarder role unattached (Rule 4 violation).
- Putting all new runtime's inbound connectors in one `<*>` block — violates Rule 6; apply port isolation.

## Rule 10: Mediator/Bus Port Extension Topology

When decomposing a component into two halves with an existing mediator/bus (IPC, Gateway, Broker) coordinating between them, two extension patterns apply:

**Rule 10A — Receiver-then-forwarder on an existing platform port (Rule 6):**
If an existing platform/infrastructure port must now also forward to a new consumer in the split-off component, extend it in-place using `<*>` with the input role first and the forwarder output role second. Do NOT create a second port unless the semantics conflict.

```wright
-- Existing port extended as receiver + forwarder:
attach Platform.recv_sandbox() = upstream.receiver() <*> seccomp_to_cr.forwarder(201);
--                               ^^ input (first)       ^^ new output (second)
```

**Rule 10B — New dedicated ports on an existing mediator/bus:**
When the decomposition introduces new communication lanes (component A → mediator → component B), add new ports to the mediator — one per new lane. Do NOT modify or reuse existing port attach statements. Fresh connector instances pair with each new mediator port. All existing ports and their attach statements remain unchanged.

```wright
component IPC {
  -- Existing ports (unchanged):
  port recv_renderer() = delivered_renderer -> recv_renderer();
  -- New ports for new lanes added during decomposition:
  port ipc_tab_to_cr() = tab_to_cr -> ipc_tab_to_cr();   -- new lane A → mediator → B
  port ipc_cr_to_cb()  = cr_to_cb_ipc -> ipc_cr_to_cb();  -- new lane B → mediator → A
}
-- Fresh connector instances for each new lane:
declare cb_to_ipc_tab = CHAINConnector;
declare ipc_to_cr_render = CHAINConnector;
attach IPC.ipc_tab_to_cr() = cb_to_ipc_tab.handler() <*> ipc_to_cr_render.forwarder(302);
-- Existing IPC.recv_renderer() attach is untouched
```

**Anti-patterns:**
- Reusing an existing mediator port to carry a new unrelated lane — risks attach conflict and semantic confusion.
- Creating a second platform port when the existing port can handle receiver + forwarder in Rule 6 order.
- Adding new output roles to an existing connector instance that already carries mixed attachments — use a fresh connector instance instead (wire-reuse exception from Rule 6).

## Usage Guidance

- When adding a new connector: determine which role is input and which is output by checking which role sends first (`ch!j`) and which receives first (`ch?j`).
- When writing `<*>` attachments: put the input role first, then all output roles.
- When a component receives from N connectors: declare N separate ports (one per input connector).
- When a component fans out to N consumers from one input: use a single port with the input role first, then N output roles (may mix connector types freely).
- When splitting a backend into specialized backends: apply the backend decomposition topology (Rule 6 above). Choose between point-to-point CSConnector per caller (Variant A, for library/service splits), frontend fan-out (Variant B, for gateway patterns), storage-tier decomposition (Variant C, for hot/cold store + coordinator splits), or utility-split (Variant D, for cross-cutting service decomposition into domain utilities). In all cases apply port isolation on the new backends, wire reuse for inherited roles, and fan-out extension on existing services when an analytics aggregator is present. Always analyse all callers' functional domains to discover connections to the appropriate sub-backend. For Variant C, carefully count wires: each caller-store pair requires its own wire; dual-store readers need two separate output ports. For Variant D: classify every caller (including non-spec callers) by domain affinity; expand shared infrastructure providers N-fold (one port per new utility); use component-scoped port name prefixes on all new utility ports. **Wire-reuse exception**: if an existing connector wire already has multi-role mixed attachments (several components as output-role readers on the same connector instance) and the new consumer only needs a single output role, declare a new dedicated connector instance — do not extend the existing mixed wire.
- When adding streaming/real-time push connections: use IOConnector (Rule 7). One wire per consumer. Port isolation applies on the receiving component. Do not use CSConnector for fire-and-forget/streaming semantics.
- When a stream-receiving component also fans out to downstream services: use the IOConnector fan-through variant — blockstorage() input role first, then output roles (CSConnector requester, PSConnector publisher, WRConnector writer, etc.) in the same `<*>` block. No extra port isolation needed if there is only one IOConnector input role.
- When migrating a frontend from server-rendered to API-driven: apply Rule 8. Remove all direct frontend-to-service wires, route via APIGateway, add BFF for composite calls, add component-scoped ports to existing services, use a custom connector for CDN. Explicitly account for all removed and added wires.
- When retiring a plugin or runtime subsystem and replacing it with a new runtime: apply Rule 9. Introduce a Bridge to replace the old forwarder, promote existing pass-through components to middlemen with a new input port, and re-attach any connector slots that pointed to the retired component onto the new runtime. Apply port isolation on the new runtime for each of its inbound connectors.
- When decomposing a component into two halves mediated by an existing bus/IPC: apply Rule 10. Extend existing platform ports in-place (receiver first, forwarder second) rather than creating new ports. Add new dedicated ports to the mediator for each new lane — never modify existing mediator port attach statements.
