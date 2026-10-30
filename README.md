# LegalAI

A legal AI harness built for **reliability and accuracy**: every legal claim is grounded in an exact,
versioned source span and independently verified before it reaches a user.

## Layout

```
AGENTS.md                 Constitution for all agents (start here)
CLAUDE.md                 One-line import of AGENTS.md for Claude Code
docs/
  PROJECT.md              Goals, roadmap, open decisions
  PRINCIPLES.md           Non-negotiable reliability rules (P1–P9)
  ORGANIZATION.md         Departments, ownership, dependency rules, communication protocol
  standards/              Documentation, code, legal-content standards
  templates/              REQ / ADR / CHARTER templates
  adr/                    Architecture decisions
  requirements/           Requirement documents between departments
departments/
  contracts/              architecture  — shared data models and ports (only shared code)
  casefile/               confidential case documents, CaseFileStore
  corpus/                 legal sources, versions, provenance, SourceStore
  retrieval/              indexing and search, Retriever
  reasoning/              agent harness, Answerer
  verification/           independent claim/citation checks, Verifier
  evaluation/             golden sets, metrics, release gate
  interface/              composition root, CLI/API
.claude/agents/           one subagent per department
scripts/                  check_all, check_boundaries, check_docs
```

## Quick start

```sh
uv sync
uv run python scripts/check_all.py
```
