# evaluation department — agent rules

You are acting for the **evaluation** department. The root `AGENTS.md` and `docs/PRINCIPLES.md` apply in full.

Read `CHARTER.md` in this directory before acting — it defines this department's scope and interfaces.

## Scope
- You MAY edit: `departments/evaluation/**`, REQs your department issues (`docs/requirements/REQ-EVALUATION-*.md`, §1–§6), and §7–§8 of REQs addressed to you.
- Everything else is read-only. Need a change elsewhere → write a REQ (`docs/templates/REQ.md`).
- Other departments' code is visible to you but is NOT your interface — only `legalai_contracts` and public `__all__` are.

## Working loop
1. Read the REQ you were assigned and this charter. If acceptance criteria are untestable or conflict
   with principles, respond in REQ §7 instead of starting.
2. Implement inside your package. Keep the public API in `src/legalai_evaluation/__init__.py` `__all__`.
3. Run `uv run python scripts/check_all.py` from the repo root. Fix, never weaken checks.
4. Fill REQ §8 (what changed, how to verify, evidence, limitations); set `status: delivered`.
