---
id: CHARTER-ARCHITECTURE
owner: architecture
status: active
updated: 2026-10-30
---

# Architecture Charter (package: `legalai_contracts`)

## Mission
Keep the departments independent and the system coherent: own the shared contracts, standards and decisions.

## Owns
- `departments/contracts/` — data models and port `Protocol`s shared by all departments.
- `docs/PRINCIPLES.md`, `docs/ORGANIZATION.md`, `docs/standards/`, `docs/templates/`, `docs/adr/`.
- `scripts/`, root `pyproject.toml`, root `AGENTS.md` / `CLAUDE.md`, `.claude/`.

## Does not own
Any business logic: parsing (corpus), ranking (retrieval), drafting (reasoning), checking
(verification), metrics (evaluation), delivery (interface).

## Interfaces
- **Consumes:** nothing internal.
- **Provides:** `legalai_contracts.__all__`; `CONTRACT_VERSION` (semver).

## Quality bars
- Contracts contain no I/O, no network, no model calls; only `pydantic` as a dependency.
- Every validator that encodes a principle has a test.
- Breaking change → MAJOR bump + ADR + migration notes in the requesting REQ.

## Reliability duties
P1 (verbatim-quote and grounding validators), P3 (fail-closed report validator), P4 (mandatory
jurisdiction and as-of fields), P5 (provenance fields, `ModelTrace`).
