---
id: backend-split-decomposition-topology
type: design-pattern
scope: attach-design
status: active
tags: [decomposition, backend-split, analytics, fan-out, port-isolation, wire-reuse, routing, multi-backend, hot-cold-storage, lifecycle-coordinator, storage-tier, utility-split, shared-infrastructure, configuration-fanout, domain-affinity]
confidence: 0.94
references: 8
skill_ref: .claude/skills/reusableskill-connector-rules/SKILL.md
---

## Context

When a single backend component is decomposed into two or more specialized backends (e.g. a monolithic third-party library group split into math/image/GPU/viz backends, or an ops backend and analytics backend, a unified database split into hot-storage + cold-storage + lifecycle coordinator, or a cross-cutting utility service split into domain-specific utilities), the system requires routing each caller to the appropriate sub-backend, isolating input ports on each new backend, and optionally extending existing services with fan-out when an analytics aggregator is present.

**Storage-tier decomposition variant:** When a database or store is split into hot-storage (active/recent data) + cold-storage (archived/historical data) + coordinator (lifecycle/migration manager), callers must be separately extended with new output ports for each store they need to write to or read from; the coordinator connects to both stores via its own dedicated wires; and services with dual-store reads (e.g. fetching both active and archived records) must declare two separate output roles — one per store — keeping port isolation on each store's inbound port.

**Utility-split variant:** When a cross-cutting utility service (e.g. a shared utility providing tools to many domain components) is split into N domain-specific utilities, the decomposition follows Variant A (point-to-point CSConnector per caller) but requires additional steps: (1) classify all callers by domain affinity to determine which new utility they connect to — some callers may not be specified by the task and must be assigned by functional reasoning; (2) shared infrastructure adapters (e.g. configuration/preferences providers, shared resource stores) that previously had one port to the monolithic utility must expand to N ports — one per new domain utility — since each utility becomes an independent input role; (3) each shared provider gains one new connector wire per new utility. This variant also applies when splitting a monolithic UI/view component into N domain-view components plus a coordinator (e.g. Archipelago → StructureView + BehaviorView + DeploymentView + ViewCoordinator): each view declares component-scoped port prefixes (sv_*, bv_*, dv_*, vc_*); the coordinator holds state-sync ports to all views; and cross-provider components (GraphLayoutPrefs, SelectorDriver, SharedEditorInfrastructure) expand N-fold to reach each new view independently. Cross-view liveness assertions (e.g. SV selector-recv → BV → DV chain) should be included to verify coordinator-mediated interaction paths.

## Distilled Rule

When splitting one backend into N specialized backends:

1. **Routing topology (choose one):**
   - *Point-to-point CSConnector per caller* (most common for library/service decomposition): each caller declares one separate CSConnector wire to the specific sub-backend it needs; no fan-out port required. Each caller's `call_<sub>` port uses a dedicated CSConnector as the output (requester) role.
   - *Fan-out from a routing frontend*: a single frontend port fans out to all N sub-backends via a `<*>` attachment with one CSConnector requester per sub-backend.
2. **Port isolation on new backends**: each new backend must declare one separate port per inbound connector — the new backend is the input side of each (apply `port-isolation-for-dual-input-roles`). Use `<sub>_srv_<caller>` naming for clarity.
3. **Analytics aggregator fan-out** (only when an analytics aggregator pattern applies): existing services that must now also feed the analytics backend extend their existing port using Rule 6 fan-out — add the new PSConnector/WRConnector output role after the existing input role (apply `psconnector-fanout-multi-role-topology`). Declare one `<*>` attachment per service with the existing input role first, then the new output role.
4. **Wire reuse on role inheritance**: if a new component takes on the same role in an existing connector wire as the replaced component, reuse that wire rather than creating a new one (update only the attach statement's component reference). **Exception:** do NOT reuse a wire when the existing wire already carries multi-role mixed attachments (i.e., other components are attached as readers/pollers via mixed output roles on the same connector instance) and the new consumer only needs a single output role. In that case, declare a fresh connector instance to avoid inheriting unsafe multi-role mixing.
5. **Caller analysis for new connections**: during decomposition, analyse each caller's functional domain (e.g. image, GPU, math) to determine which sub-backend it routes to; some callers may gain a new connection not present before the split (e.g. GroupNumerics → ThirdPartyMath when previously both were under a monolith).
6. **Storage-tier decomposition (hot/cold + coordinator):** When splitting a data store into hot-storage + cold-storage + lifecycle coordinator:
   - Each caller (writer or reader) that touches both stores must be extended with a new output port for each store it writes to or reads from — use point-to-point CSConnector wires (Variant A).
   - The coordinator connects to both stores via its own wires (one to hot-store for read/promote, one to cold-store for write/archive).
   - Services with dual-store reads (e.g. fetching recent from hot and historical from cold) must declare two separate output roles in the same port or across separate ports, one targeting each store — apply port isolation on each store's inbound port.
   - Count wires carefully: N callers × M stores they touch = N×M wires (avoid under-declaring).

## Example

**Variant A — Point-to-point CSConnector per caller (library/service decomposition into N typed backends):**
```wright
-- Each caller gets a dedicated wire to the specific sub-backend it needs
declare cor_to_tpm = CSConnector;   -- GroupCore → ThirdPartyMath
declare iox_to_tpi = CSConnector;   -- GroupIO → ThirdPartyImage
declare flt_to_tpg = CSConnector;   -- GroupFiltering → ThirdPartyGPU
declare brg_to_tpv = CSConnector;   -- GroupBridge → ThirdPartyViz

-- Caller's output (requester) role:
attach GroupCore.cor_call_tpm() = cor_to_tpm.requester(16);
-- Sub-backend's input (responder) port — one port per inbound caller:
attach ThirdPartyMath.tpm_srv_cor() = cor_to_tpm.responder();
```

**Variant B — Fan-out from a routing frontend:**
```wright
-- Frontend gains one output role per new backend in the same <*> block
ShopFrontend.shop() <*> shopopswire.requester(o) <*> shopanalyticwire.requester(a);
```

**Analytics aggregator with N input ports (one per upstream source):**
```wright
component AnalyticsBackend {
  port analyticsrpt()        = shopanalyticwire.responder() <*> ...;   -- from frontend
  port analyticsorderevt()   = ordereventwire.subscriber() <*> ...;    -- from OrdersService
  port analyticspaydata()    = payanalyticwire.subscriber() <*> ...;   -- from Payment
  port analyticsshipdata()   = shipanalyticwire.subscriber() <*> ...;  -- from ShippingService
}
-- Four separate ports: one per inbound connector (input-role isolation)
```

**Extending existing service to fan out to analytics (Rule 6, input role first):**
```wright
-- Payment.pay() was: paywire.writestorage() only
-- After split: add analytics publisher output role
Payment.pay() <*> paywire.writestorage() <*> payanalyticwire.publisher(102);
--              ^^ input role (first)     ^^ new output role (second)
```

**Wire reuse: OpsBackend inherits ShopBackend's role in existing orderquerywire:**
```wright
-- Was: ShopBackend.listorder() <*> orderquerywire.requester(o) <*> ...
-- After: OpsBackend.listorder() <*> orderquerywire.requester(o) <*> ...
-- The wire is unchanged; only the source component changes in the attach statement
```

**Variant C — Storage-tier decomposition (hot/cold + lifecycle coordinator):**
```wright
-- OrdersDB split into ActiveOrdersDB (hot) + OrderArchive (cold) + OrderLifecycleManager (coordinator)
-- 12 new wires declared: one per caller-store pair

-- Callers extended with new output ports for each store they touch:
attach ShopFrontend.actdb_frontend() = fe_to_actdb.requester(f);    -- read active
attach Payment.payment_arch_read()   = pay_to_arch.requester(p);    -- read archive
attach Payment.payment_actdb_write() = pay_to_actdb.requester(p2);  -- write active

-- Each store has isolated inbound ports (one per inbound caller):
component ActiveOrdersDB {
  port actdb_write()    = fe_write_wire.responder() <*> ...;   -- from ShopFrontend write
  port actdb_frontend() = fe_to_actdb.responder() <*> ...;     -- from ShopFrontend read
  port actdb_payment()  = pay_to_actdb.responder() <*> ...;    -- from Payment
  port actdb_carts()    = carts_to_actdb.responder() <*> ...;  -- from CartsService
  -- ... one port per inbound caller
}

-- Coordinator connects to both stores:
attach OrderLifecycleManager.lifecycle_readactive() = olm_to_actdb.requester(r);
attach OrderLifecycleManager.lifecycle_writearchive() = olm_to_arch.requester(w);
attach ActiveOrdersDB.actdb_lifecycle()  = olm_to_actdb.responder() <*> ...;
attach OrderArchive.arch_migrate()       = olm_to_arch.responder() <*> ...;
```

**Variant D — Utility-split (cross-cutting service decomposed into N domain utilities):**
```wright
-- ArchStudioUtils split into EditorUtils, AnalysisUtils, ModelUtils, ViewUtils
-- Each caller is classified by domain affinity:
--   EditorUtils callers: EditorManager, ArchEdit, SharedEditorInfrastructure, Launcher, FileManager
--   AnalysisUtils callers: Archlight, TypeWrangler, GuardTracker, Schematron, SelectorDriver
--   ModelUtils callers: XArchADT, XArchChangeSet, ChangeSetUtils, CSRM, Meta
--   ViewUtils callers: Archipelago, GraphLayout, RationaleView, TracelinkView

-- Point-to-point per caller (same as Variant A):
declare em_to_edutil = CSConnector;   -- EditorManager → EditorUtils
declare arch_to_anutil = CSConnector; -- Archlight → AnalysisUtils
attach EditorManager.em_to_edutil_port() = em_to_edutil.requester(j);
attach EditorUtils.editorutils_srv_em() = em_to_edutil.responder();  -- component-scoped prefix

-- Shared infrastructure providers expand N-fold (e.g. PreferencesADT 1→4 ports):
component PreferencesADT {
  port padt_to_editorutils()  = padt_to_edutil.responder() <*> ...;  -- was one port to ArchStudioUtils
  port padt_to_analysisutils() = padt_to_anutil.responder() <*> ...;
  port padt_to_modelutils()   = padt_to_modutil.responder() <*> ...;
  port padt_to_viewutils()    = padt_to_viewutil.responder() <*> ...;
}

-- Resources similarly expands from 1 port to 4 (one per new utility):
component Resources {
  port editorutils_res()  = edutil_to_res.responder() <*> ...;
  port analysisutils_res() = anutil_to_res.responder() <*> ...;
  port modelutils_res()   = modutil_to_res.responder() <*> ...;
  port viewutils_res()    = viewutil_to_res.responder() <*> ...;
}
```

## Anti-pattern

- Creating a new wire for each new backend when the frontend could fan-out to both using a single `<*>` port statement.
- Declaring one large port on the analytics aggregator that tries to receive from all upstream sources (violates Rule 6: multiple input roles in one `<*>` block).
- Discarding and recreating wires when the decomposed component's successor plays the same role — reuse the existing wire.
- Reusing an existing connector wire when it already carries multi-role mixed attachments (other output-role readers on the same connector instance) and the new consumer only needs a single output role — this risks unsafe multi-role mixing; use a new dedicated connector instance instead.
- Failing to analyse all callers' functional domains — missing a caller-to-sub-backend connection (e.g. a numerics component that implicitly depended on the monolith's math capability).
- In storage-tier decomposition: forgetting to extend a caller (e.g. ShippingService, CartsService) with new ports for the hot store even though it was not a caller of the original monolithic DB directly — re-analyse all callers that need real-time write access.
- In storage-tier decomposition: under-counting wires by assuming one wire handles both stores for a dual-reader service; each store requires a separate wire and port.
- In utility-split decomposition: forgetting to expand shared infrastructure providers (config/prefs, resource stores) — leaving them with a single port to the old monolithic utility means they cannot connect to all N new domain utilities; every shared provider must gain N ports.
- In utility-split decomposition: using generic port names on new utilities (e.g. `serve_em`) without component-scoped prefix — with N new components declaring similar serve ports, Rule 1 global uniqueness violations are near-certain; always prefix with the new component name (e.g. `editorutils_srv_em`).
