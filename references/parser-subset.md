# Parser subset

Read this when changing `scripts/links_validate.py`, adding examples, or writing
cards by hand. The validator intentionally implements a small Markdown and YAML
subset so the toolkit stays dependency-free and predictable.

## Supported frontmatter subset

Markdown cards and staged proposals use one fenced YAML-like frontmatter block at
the top of the file:

```markdown
---
id: c-example
type: concept
status: candidate
source: example-source
owner: ontology-operator
last-reviewed: 2026-06-22
next-audit: 2026-09-22
attrs:
  subtype: metric
links:
  measured-by: [lead-quality]
---
```

The parser supports:

- plain scalar strings, booleans (`true` / `false`), and empty-free values;
- nested mappings by indentation;
- block lists with `- item`;
- inline lists like `[role-a, role-b]`;
- fenced candidate cards inside staged proposal bodies;
- one `source-map table` in `02-source-map.md` with columns for Source id,
  Trust, Owner, Access mode, Read policy, and Meaning.

## Unsupported YAML features

Do not use these in ontology frontmatter:

- anchors, aliases, tags, merge keys, or multi-document YAML;
- quoted scalars that rely on YAML escape semantics;
- folded or literal block scalars inside frontmatter;
- complex inline objects;
- comments as meaningful data;
- escaped pipes inside `02-source-map.md` table cells.

The source-map table splitter is deliberately simple: a pipe splits a cell. If a
source locator contains a pipe, describe it in prose or move the exact locator to
the proposal body rather than escaping it in the table.

## Why this is strict

The validator is a launch gate, not a general YAML engine. A small parser makes
agent output easier to inspect, keeps examples portable, and avoids dependency
setup for first-session ontology work. If the repository later needs full YAML or
JSON Schema runtime validation, add that as a deliberate migration and keep this
document as the compatibility boundary for existing cards.
