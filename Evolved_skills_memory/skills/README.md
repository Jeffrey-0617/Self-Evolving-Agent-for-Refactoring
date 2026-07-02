# Evolved Skills

Each subfolder is one skill created or updated by the agent. A skill is a `SKILL.md` file containing reusable procedural instructions the agent invokes during a task.

There are two kinds of skills:

---

## Script-based Skills

These skills are backed by a static analysis tool (a Python script in `tools/`). The skill defines when to invoke the tool, how to interpret its output, and what failure cases to expect.

**Example: [`check-port-name-uniqueness`](check-port-name-uniqueness/SKILL.md)**

Verifies that every port name is globally unique across all components in the ADL. A collision between two components causes verification failure — often surfacing as a misleading assertion error rather than a naming conflict. Backed by [`check_port_name_uniqueness.py`](../tools/check_port_name_uniqueness/check_port_name_uniqueness.py).

Usage:
```bash
python3 Evolved_skills_memory/tools/check_port_name_uniqueness/check_port_name_uniqueness.py tmp/refactored.adl
```

Key failure case documented in the skill:
```wright
-- Two components both declare a port named 'reminder' → ERROR
component PassengerUI {
  port reminder() = passengerreminded -> reminder();
}
component DriverUI {
  port reminder() = driverreminded -> reminder();  -- DUPLICATE: violates Rule 1
}

-- Fix: prefix port names with the component name
component PassengerUI {
  port passengerreminder() = passengerreminded -> passengerreminder();
}
component DriverUI {
  port driverreminder() = driverreminded -> driverreminder();
}
```

Other skills with tools: [`check-assertion-events`](check-assertion-events/SKILL.md), [`check-role-param-integers`](check-role-param-integers/SKILL.md), [`check-adl-no-asserts`](check-adl-no-asserts/SKILL.md)

---

## Guidance Skills

These are pure knowledge rules — design guidelines, assertion-writing rules, or diagnostic heuristics with no executable component.

**Example: [`reusableskill-connector-rules`](reusableskill-connector-rules/SKILL.md)**

Reusable design rules for Wright# connectors and multi-role port attachments. No tool is invoked — the skill provides rules the agent applies when designing or refactoring connector structures.

Key rule example (Rule 2 — multi-role attachment ordering):

```wright
-- WRONG: two input roles in one <*> attach (violates Rule 6)
OrdersService.receive() <*> riskorderwire.responder() <*> overridewire.responder();

-- CORRECT: one input role per port (port isolation, Rule 3)
component OrdersService {
  port receiveclearance() = riskorderwire.responder() <*> ...;
  port receiveoverride()  = overridewire.responder() <*> ...;
}
```

Another key rule (Rule 1 — input role always first in `<*>`):

```wright
-- CORRECT: input role first, then output roles
Payment.pay() <*> paywire.writestorage() <*> fraudpaymentwire.writer(99);
--              ^^ input role (first)     ^^ output role (second)
```

The skill covers 10 rules across topology patterns: fan-out, backend decomposition, streaming (IOConnector), API gateway migration, plugin retirement, and mediator/bus extension.

Other skills without tools: [`reusableskill-assertion-design`](reusableskill-assertion-design/SKILL.md), [`reusableskill-verification-diagnostics`](reusableskill-verification-diagnostics/SKILL.md)

---

