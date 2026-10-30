---
id: ADR-0001
title: Departmental monorepo with a shared contracts package
owner: architecture
status: accepted
deciders: [project owner]
updated: 2026-10-30
---

# ADR-0001: Departmental monorepo with a shared contracts package

## Context
The project will be built largely by multiple AI agents working in parallel. Agents working on
one area must not break another, and the overall system must stay auditable (P2, P5).

## Options considered
| Option | Pros | Cons | Reliability impact |
|---|---|---|---|
| Single package, free imports | Fastest start | Agents collide; generation and verification entangle | Bad: P2 cannot be guaranteed |
| Multi-repo per department | Strong isolation | Heavy coordination, version drift | Neutral |
| **Monorepo, uv workspace, one package per department, shared contracts only** | Isolation + atomic changes + one CI | Requires boundary enforcement | Good: boundaries are machine-checked |

## Decision
1. One `uv` workspace. Each department is a member package under `departments/<name>/`.
2. `legalai_contracts` (owned by architecture) is the only package all departments may import.
   It contains data models and port `Protocol`s only — no business logic, no I/O.
3. Core departments (corpus, retrieval, reasoning, verification) depend only on contracts.
   `interface` is the composition root. `evaluation` tests everything through public APIs.
4. `scripts/check_boundaries.py` enforces the dependency rules in `docs/ORGANIZATION.md` §4.
5. Python ≥ 3.12; Pydantic v2; ruff; mypy strict; pytest.

## Consequences
- Cross-department needs go through REQs; contract changes are serialized through architecture.
- Some small duplication between departments is accepted as the price of independence.

## Validation
Boundary check passes in CI on every change. Revisit if contract churn exceeds one breaking change per month.
