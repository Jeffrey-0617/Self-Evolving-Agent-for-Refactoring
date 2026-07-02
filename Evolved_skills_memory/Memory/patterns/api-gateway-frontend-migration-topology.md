---
id: api-gateway-frontend-migration-topology
type: design-pattern
scope: attach-design
status: active
tags: [api-gateway, BFF, frontend-migration, server-rendered, api-driven, wire-removal, routing, CDN, custom-connector, architecture-migration]
confidence: 0.88
references: 2
skill_ref: .claude/skills/reusableskill-connector-rules/SKILL.md
---

## Context

When migrating a frontend component from a server-rendered (direct backend connections) to an API-driven architecture, all direct frontend-to-service wires must be replaced with routing through an APIGateway component. A Backend-for-Frontend (BFF) aggregator is introduced to compose multiple backend calls. A CDN integration component may be added for static asset delivery. Existing backend services gain new component-scoped ports for the new API paths.

## Distilled Rule

When migrating frontend architecture from server-rendered to API-driven:

1. **Remove all direct frontend-to-service wires**: replace every `CSConnector` wire from the frontend directly to a backend service with a wire from the frontend to the APIGateway. The frontend gains a separate port per entry point (e.g. `frontend_browse`, `frontend_login`, `frontend_order`, `frontend_cdn`).

2. **APIGateway as the routing hub**: the APIGateway receives all frontend traffic and routes to backend services or the BFF. Declare one port per inbound frontend path (input side: apply port isolation, Rule 3). Declare one output port per downstream target — output roles may be CSConnector requesters toward the BFF or individual backend services.

3. **BFF aggregator for composite calls**: the BFF receives traffic from the APIGateway and fans out to multiple backend services. One port per inbound APIGateway connector (port isolation), plus one output role per backend in a `<*>` fan-out statement (or separate ports when the BFF itself is the input side of backend responses).

4. **Existing backend services: add component-scoped ports for the new API path**: when an existing service must now be reached via the new API path (instead of via the old direct wire), add a new port named with the service prefix (e.g. `ordersservice_api`, `payment_api`, `shippingservice_track`, `shopbackend_mgmt`). The old port used by the removed wire can be renamed or removed.

5. **CDN integration via custom connector**: for CDN-served static assets, declare a custom connector (e.g. `CDNConnector`) with `cdnclient` (output role, process first) and `cdnserver` (input role, receives first). The frontend gains a `frontend_cdn` port (output role); CDNIntegration gains a `cdn_serve` port (input role).

6. **Port naming**: all new ports must be component-scoped (prefixed with the component name) to satisfy global uniqueness (Rule 1).

7. **Wire count**: expect a net wire reduction on the frontend side (old direct wires removed) and a net increase overall (new gateway + BFF wires). Count removed wires explicitly to avoid leaving orphaned attach statements.

## Example

```wright
-- Before: ShopFrontend routes directly to each backend service
-- (wires: catelequewire, userwire, cartwire, orderwire — all removed)

-- After: ShopFrontend routes through APIGateway
declare frontend_browse_wire = CSConnector;    -- ShopFrontend → APIGateway (browse)
declare frontend_login_wire  = CSConnector;    -- ShopFrontend → APIGateway (login)
declare frontend_order_wire  = CSConnector;    -- ShopFrontend → APIGateway (order)
declare cdn_wire             = CDNConnector;   -- ShopFrontend → CDNIntegration

-- ShopFrontend: one port per entry point (all output roles — it is the requester)
attach ShopFrontend.frontend_browse() = frontend_browse_wire.requester(b);
attach ShopFrontend.frontend_cdn()    = cdn_wire.cdnclient(a);

-- APIGateway: one input port per frontend path (port isolation, Rule 3)
component APIGateway {
  port apigateway_browse() = frontend_browse_wire.responder() <*> apigateway_bff_browse_wire.requester(x);
  port apigateway_login()  = frontend_login_wire.responder()  <*> bff_auth_wire.requester(y);
  -- one separate port per inbound frontend connector
}

-- BFF: input side of APIGateway wires; fans out to backends
component BFFService {
  port bff_browse() = apigateway_bff_browse_wire.responder() <*> bff_catalogue_wire.requester(c) <*> bff_carts_wire.requester(d);
  -- responder() input role first, then output roles to each backend
}

-- Existing service gains a new component-scoped port for the API path:
-- (old port 'postorder' removed; new port 'ordersservice_api' added)
attach OrdersService.ordersservice_api() = bff_orders_wire.responder() <*> ...;

-- CDN integration via custom connector:
declare cdn_wire = CDNConnector;
attach ShopFrontend.frontend_cdn()     = cdn_wire.cdnclient(a);   -- output role
attach CDNIntegration.cdn_serve()      = cdn_wire.cdnserver();    -- input role
```

## Anti-pattern

- Keeping direct frontend-to-service wires alongside the new gateway wires (orphaned wires cause Rule 4 failures — incomplete attachments or double-attachment).
- Placing all inbound frontend paths onto one APIGateway port (violates Rule 6 / Rule 3: multiple input roles in one `<*>` block).
- Forgetting to add new component-scoped ports to existing backend services that now receive traffic via BFF instead of directly from the frontend.
- Not removing the old ports of existing services that were only connected to the now-removed direct wires (leaves unattached ports).
- Using CSConnector for CDN delivery (CDN is push/serve with no CSP reply; use a custom connector or IOConnector).
