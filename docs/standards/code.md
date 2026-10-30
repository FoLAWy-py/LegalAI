---
id: STD-CODE
owner: architecture
status: active
updated: 2026-10-30
---

# Code Standard

## 1. Stack

- Python ≥ 3.12, managed with `uv` as a workspace (one member per department). See ADR-0001.
- Data crossing any boundary: Pydantic v2 models from `legalai_contracts`.
- Lint/format: `ruff`. Types: `mypy --strict`. Tests: `pytest`.

## 2. Structure of a department package

```
departments/<name>/
  CHARTER.md          # mission, scope, interfaces, quality bars
  AGENTS.md           # agent rules for this department
  CLAUDE.md           # imports only: @AGENTS.md @CHARTER.md
  pyproject.toml
  src/legalai_<name>/
    __init__.py       # public API — the ONLY thing other departments may import
    ...               # internals, free to change without notice
  tests/
  docs/               # optional department notes
```

## 3. Rules

1. **Boundaries:** obey `docs/ORGANIZATION.md` §4. Never import another department's submodules.
2. **Typed everything:** no `Any` in public signatures. Model outputs are parsed into Pydantic models;
   a parse failure is an error, never silently coerced.
3. **No silent fallbacks.** Do not catch broad exceptions and continue. A failure that could affect
   legal correctness MUST surface as an error or an abstention with a reason.
4. **Immutability:** contract models are frozen. Build new objects instead of mutating.
5. **Determinism:** no hidden randomness; seed it if needed. Model calls use temperature 0 unless an
   ADR says otherwise, and record a `ModelTrace`.
6. **Configuration and secrets** come from environment variables (`.env`, template `.env.example`), read
   **only by `interface`**, which injects typed config into other departments. Never commit `.env`.
   Runtime data goes under `<LEGALAI_DATA_DIR>/<department>/`; a department never reads another's data dir.
7. **Prompts** live in files (not inline strings) under `src/legalai_<name>/prompts/`, versioned per
   `documentation.md` §5.
8. **Tests:** every bug fix adds a regression test. Unit tests never call real model APIs or network;
   live tests are marked `@pytest.mark.live` and skipped by default.
9. **Dependencies:** a department adds third-party dependencies only to its own `pyproject.toml`.
   Adding a dependency to `legalai_contracts` requires architecture approval.

## 4. Definition of done

- `uv run python scripts/check_all.py` passes.
- Public API changes are reflected in the charter's Interfaces section.
- If prompts, models, retrieval or verification changed: evaluation suite run and results recorded in the REQ §8.
