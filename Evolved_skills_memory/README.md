# Evolved Skills & Memory

This folder contains the knowledge the agent accumulates across refactoring tasks. The agent starts with no memory and a fixed set of cold-start skills. As it completes tasks, it writes new skills, tools, and memory entries here.

```
Evolved_skills_memory/
├── skills/     ← New skills created or updated by the agent
├── tools/      ← Static analysis tools written by the agent
└── Memory/
    ├── patterns/   ← Generalised reusable rules extracted from completed tasks
    └── episodes/   ← Task-specific records: what happened, what failed, what fixed it
```

---

## Skills

Skills are reusable procedural instructions the agent invokes during a task. There are two kinds:

- **Script-based Skills** — the skill is backed by a static analysis tool the agent wrote. The skill describes when and how to use the tool, and what failure cases to watch for. Example: [`check-assertion-events`](skills/check-assertion-events/SKILL.md)
- **Guidance Skills** — pure guidance rules with no executable script. Example: [`reusableskill-assertion-design`](skills/reusableskill-assertion-design/SKILL.md)

See [`skills/README.md`](skills/README.md) for more details and examples.

---

## Tools

Static analysis Python scripts written by the agent to catch known error classes before formal verification. Each tool has testcases that define exactly what the tool must catch.

See [`tools/README.md`](tools/README.md) for the full list, what each tool checks, and its testcases.

---

## Memory

**Patterns** (`Memory/patterns/`) are generalised rules extracted after tasks.
**Episodes** (`Memory/episodes/`) are task-specific records.
