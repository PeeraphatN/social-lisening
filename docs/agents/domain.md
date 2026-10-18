# Domain docs

This repository uses a single-context domain documentation layout.

## Before exploring

- Read `CONTEXT.md` at the repository root when it exists.
- Read relevant decisions under `docs/adr/` when they exist.
- If these files do not exist, proceed without flagging their absence. Create them lazily when domain terms or architectural decisions need a durable record.

## Vocabulary

Use terms defined in `CONTEXT.md` in issue titles, specs, plans, tests, and code. Do not replace a defined term with a synonym. If a needed concept is missing, reconsider the term or record the gap for domain modeling.

## Architectural decisions

Surface any conflict with an existing ADR instead of silently overriding it. State which ADR conflicts and why the decision may need to be reopened.

## Layout

```text
/
├── CONTEXT.md
└── docs/
    └── adr/
        └── NNNN-short-decision-name.md
```
