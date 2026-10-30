# LegalAI — Agent Constitution

<!-- Source of truth for all coding agents. CLAUDE.md files only import AGENTS.md (docs/standards/documentation.md §6). -->

This file binds every agent (human or AI, main session or subagent) working in this repository.
Read it fully before acting. Department-level `AGENTS.md` files add rules; they never relax these.

## 1. What this project is

A harness for legal AI: answering legal questions and analysing legal documents with
**reliability and accuracy as the overriding goals**. Speed, cost and features are secondary.
When a trade-off exists, choose the option that makes wrong answers less likely or more visible.

Required reading, in order:
1. `docs/PRINCIPLES.md` — the non-negotiable reliability rules.
2. `docs/ORGANIZATION.md` — departments, ownership, dependency rules, communication protocol.
3. `docs/standards/` — documentation, code and legal-content standards.

## 2. Hard rules (violations block merge)

1. **Know your department.** Before editing, state which department you act for. You may only
   modify files that department owns (see `docs/ORGANIZATION.md` §2). Everything else is read-only.
2. **Need something from another department? Write a requirement.** Create a REQ in
   `docs/requirements/` using `docs/templates/REQ.md`. Never edit another department's code "just to unblock".
3. **Departments share only `legalai_contracts`.** Never import another department's internals.
   `uv run python scripts/check_boundaries.py` enforces this.
4. **Never fabricate law.** Do not invent statutes, cases, citations, quotes, or holdings — not in
   code, prompts, tests, fixtures, or docs. Test fixtures use the fictional jurisdiction `ZZ`
   (see `docs/standards/legal-content.md`).
5. **Every legal assertion is traceable** to an exact source span (document, version, offsets).
   No source → no claim. Uncertain → abstain. See `docs/PRINCIPLES.md`.
6. **Run the checks before declaring work done:**
   ```sh
   uv run python scripts/check_all.py
   ```
   Report failures honestly; never weaken a test, threshold, or validator to get green.

## 3. Working as the coordinator (main session)

The main session acts as the **Program Office**: it reads REQs, dispatches work to department
subagents (`.claude/agents/<department>.md`), and verifies deliveries against acceptance criteria.
It does not write department code itself unless explicitly acting as that department.

## 4. Commands

| Task | Command |
|---|---|
| Install / sync | `uv sync` |
| All checks | `uv run python scripts/check_all.py` |
| Tests | `uv run pytest` |
| Lint / format | `uv run ruff check . && uv run ruff format --check .` |
| Types | `uv run mypy -p legalai_<dept>` |
| Boundaries | `uv run python scripts/check_boundaries.py` |
| Doc metadata | `uv run python scripts/check_docs.py` |
