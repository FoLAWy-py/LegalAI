---
id: REQ-PMO-0007
title: Re-scope v1 to CN criminal cases in ADRs, project brief and contracts
from: pmo
to: architecture
owner: pmo
status: verified
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0007: Re-scope v1 to CN criminal cases in ADRs, project brief and contracts

## 1. Context
Project owner decisions (2026-10-30), given to the Program Office in session:
- **D6 revised:** the v1 practice area is **criminal cases**, replacing civil contract disputes, with **financial crimes**
  as the v1 focus (owner answer, same day). The v1 pilot is SPP 检例第175号 (REQ-PMO-0008).
- **Sequencing:** CN first; US law is considered only after the CN vertical slice is confirmed end to end.
- **Origin approval** for corpus is delegated to the Program Office (rule in REQ-PMO-0002 §2.1).

Wave 1 REQs PMO-0002 and PMO-0005 have already been revised. The binding records (ADR-0005, `docs/PROJECT.md`)
and the contracts still say civil contract disputes. Under ORGANIZATION §5, a decision is binding only once it is written into an ADR or REQ.

## 2. Requirement
1. Architecture MUST record the change in an ADR: amend ADR-0005 or supersede it with a new ADR. It covers:
   - The use case stays an evidence outline with gaps, now for a **charged offence**: elements of the offence (犯罪构成)
     grounded in law, evidence links from case files, and gaps.
   - Defences and justifications are represented, either as contradicting links or as their own elements. State which.
   - Burden and standard of proof are cited from law and never asserted from memory.
   - The CN legal scope matches REQ-PMO-0002 §2.2.
   - The US scope is marked deferred, so D7/D8 are re-opened for the criminal context.
2. `docs/PROJECT.md` MUST be updated: D6 revised (criminal); D7/D8 deferred; CN-first sequencing; origin approval delegated
   to PMO; roadmap step 3 reads "CN criminal first".
3. Contracts MUST support a criminal outline without breaking existing users:
   - add a prosecution party role to `PartyRole`;
   - make docstrings for `cause_of_action` / `Element` cover a charged offence;
   - bump `CONTRACT_VERSION` minor, with no field removed or renamed.
   If a breaking change seems necessary, stop and report it instead.
4. Charters and other department-owned files are NOT edited. Departments update their own charters.

## 3. Interface
`PartyRole`, `LegalQuery`, `EvidenceOutline`, `Element` (`legalai_contracts`).

## 4. Acceptance criteria
1. An ADR with `status: accepted` records the criminal practice area, and ADR-0005 is marked accordingly (amended or superseded).
2. `docs/PROJECT.md` reflects every decision listed in §1.
3. `PartyRole` has a prosecution value; existing contract tests pass unchanged, and a new test builds a valid criminal
   `EvidenceOutline` on `ZZ` data with a prosecution `party_role`.
4. `CONTRACT_VERSION` minor bump; `scripts/check_all.py` passes.

## 5. Out of scope
US criminal scope, department charters, any department code.

## 6. Open questions
- Should a separate role for the victim / incidental civil plaintiff (附带民事诉讼原告人) be added now, or later?

## 7. Response
**Accepted** by architecture, 2026-10-30. No breaking change is needed. Plan:

1. **ADR:** ADR-0005 is accepted and therefore immutable except for status (STD-DOC §4), so it is
   **superseded** by a new ADR-0006 rather than amended. ADR-0006 carries over every ADR-0005 decision that still holds
   (D2 proof chart with gaps, D9 digital inputs, law vs case-file sources, renderings) and records the criminal
   re-scope. ADR-0005 gets `status: superseded`, `superseded_by: ADR-0006`; its body is left unchanged.
2. **Defences and justifications:** represented as `contradicts` links on the offence element(s) they would negate,
   not as their own elements. Reasons: (a) it works with contracts v0.2 shapes that Wave 1 departments are already
   building against, with no new field; (b) it matches REQ-PMO-0005 §2.1 ("a justification or defence supported by
   contradicting evidence"); (c) defence elements would break the meaning of a gap ("something that must be proved
   lacks evidence") unless a new field marked them, and outlines would fill up with unraised defences.
   Limitation: an `EvidenceLink` cites only case files, so the outline cannot cite the law that sets up a
   defence. ADR-0006 therefore forbids a link's `purpose` from stating the legal conditions or effect of a defence,
   and names the additive follow-up (an element kind field) to use if reviewers need defences grounded in law.
3. **Burden and standard of proof:** ADR-0006 states no rule about either. `Element.burden_on` is set only when the
   element's own cited `legal_basis` says who bears the burden; otherwise it stays `None`. Any statement of a
   standard of proof is a legal rule and must be cited from an ingested source (P1).
4. **Contracts:** add `PartyRole.PROSECUTION = "prosecution"`; widen the docstrings of `PartyRole`, `LegalQuery`,
   `Element`, `EvidenceOutline` and `EvidenceOutline.cause_of_action` to cover a charged offence; `CONTRACT_VERSION`
   0.2.0 → 0.3.0 (minor). No field, value or validator is removed, renamed or tightened.
5. **`docs/PROJECT.md`:** D3 (origin approval delegated to PMO), D6 revised, D7/D8 deferred and re-opened, a new D10
   row for CN-first sequencing, roadmap step 3 "CN criminal first".
6. **PMO update (2026-10-30, after acceptance; merged from `main` 87ab123):** §1 now sets **financial crimes** as the
   v1 focus and SPP 检例第175号 as the v1 pilot (REQ-PMO-0008). Both are recorded in ADR-0006 and `docs/PROJECT.md`.
   The ADR's CN scope follows the revised REQ-PMO-0002 §2.2, including the illegal-fundraising interpretations, the
   versions from 2014-01-01, and the non-criminal financial-regulation statutes the pilot cites. `.claude/worktrees/` is
   added to the root `.gitignore`. No acceptance criterion changes.
7. **Finding for PMO (no contract change made):** a `LegalQuery` has a single `as_of` date. The pilot's conduct
   (2014–2018) and judgments (2021) fall on different dates, and REQ-PMO-0008 §4.3 checks versions "on the relevant
   date (conduct period or judgment date)". Which date's law governs is a legal question for the cited sources.
   Contracts 0.3.0 cannot carry more than one reference date per outline, so ADR-0006 §6.2 records this as a
   limitation. If one outline needs law in force on more than one date, PMO should file a REQ for an additive field.

**§6 open question — recommendation: defer; do not add a victim / incidental civil plaintiff role now.**
- The v1 deliverable is an outline of the elements of a **charged offence**. A victim role is not needed to build one,
  and no Wave 1 REQ or evaluation case exercises it, so the value would be untested and every consumer would still
  have to handle it.
- An incidental civil action has a civil claim, not an offence, as its subject. If it is brought into scope, the
  existing `PLAINTIFF` role with a civil `cause_of_action` may be enough. Whether the victim (被害人) and the
  incidental civil plaintiff (附带民事诉讼原告人) need separate roles, and what procedural standing each has, are legal
  questions. They must be answered from the ingested Criminal Procedure Law sources, not decided by architecture from
  memory.
- Adding an enum value later is an additive minor bump, so deferring closes off nothing. ADR-0006 marks the incidental
  civil action as outside the v1 outline until the project owner decides; that needs a new REQ.

## 8. Delivery
Delivered by architecture, 2026-10-30, on branch `worktree-agent-a506b81174d32d74c` (based on `main` 87ab123).

**What changed**
| File | Change |
|---|---|
| `docs/adr/ADR-0006-criminal-evidence-outline.md` | New, `status: accepted`, `supersedes: [ADR-0005]`. Covers the criminal outline, party roles, burden/standard of proof (cited from law only), defences as `contradicts` links (Option A), CN scope per REQ-PMO-0002 §2.2 with the financial-crime focus, pilot SPP 检例第175号, the single-`as_of` limitation, and US deferred with D7/D8 re-opened. |
| `docs/adr/ADR-0005-evidence-outline-use-case.md` | Front matter only: `status: superseded`, `superseded_by: ADR-0006`. Body unchanged (STD-DOC §4). |
| `docs/PROJECT.md` | D2/D9 point to ADR-0006; D3 records origin approval delegated to PMO; D6 is criminal with a financial-crime focus; D7/D8 deferred and re-opened; new D10 (CN-first sequencing) and D11 (pilot SPP 检例第175号); roadmap step 3 reads "CN criminal first". |
| `departments/contracts/src/legalai_contracts/answers.py` | `PartyRole.PROSECUTION = "prosecution"` added; docstrings on `PartyRole` and `LegalQuery` cover criminal cases. |
| `departments/contracts/src/legalai_contracts/outline.py` | Docstrings on `Element` and `EvidenceOutline` cover a charged offence; `cause_of_action` gets `Field(description=...)`. It is still a required `str` with no new constraint. |
| `departments/contracts/src/legalai_contracts/__init__.py` | `CONTRACT_VERSION` 0.2.0 → **0.3.0**. `__all__` unchanged. |
| `departments/contracts/tests/test_criminal_outline.py` | New: 7 tests on synthetic `ZZ` data. |
| `docs/requirements/README.md` | Index rows added for REQ-PMO-0007 and REQ-PMO-0008 (at its own `draft` status); REQ-PMO-0002 title synced with its revised title. No other status changed. |
| `.gitignore` | `.claude/worktrees/` added (PMO request). |

**Contract diff (additive only).** One new enum value (`PartyRole.PROSECUTION`). No field, enum value, validator or
public name was removed, renamed or tightened. The existing test files `test_contracts.py` and `test_outline.py` are
byte-unchanged from the initial commit `b10f5f6` and pass. Consumers that branch on `PartyRole` must handle
`"prosecution"` or fail closed (ADR-0006 Consequences).

**How to verify**
1. AC1: `docs/adr/ADR-0006-*.md` has `status: accepted`. ADR-0005 front matter has `status: superseded`, `superseded_by: ADR-0006`.
2. AC2: `docs/PROJECT.md` rows D3, D6, D7, D8, D10, D11 and roadmap step 3.
3. AC3: `uv run pytest -q departments/contracts`. `test_valid_criminal_outline_with_prosecution_role` builds a valid
   criminal `EvidenceOutline` on `ZZ` data with `party_role=PROSECUTION`. The two pre-existing test files show no diff
   against `b10f5f6`.
4. AC4: `CONTRACT_VERSION == "0.3.0"`; `uv run python scripts/check_all.py`.

**Evidence** (`uv run python scripts/check_all.py`, 2026-10-30): boundaries OK (0 violations); docs OK (0 problems);
ruff check and format clean; mypy clean on 8 packages and scripts; pytest **34 passed** (contracts 27: 20 existing + 7
new); `ALL CHECKS PASSED`.

**Limitations / follow-ups for PMO**
- Option A means an outline cannot cite the law that sets up a defence. ADR-0006 §4.3 bars legal rules in a link
  `purpose`, and §4.4 names the additive follow-up (an element kind field) if reviewers need defences cited in the outline.
- Single `as_of` per outline (ADR-0006 §6.2, §7 item 7). The pilot may need law from more than one date; this needs a REQ for an additive field.
- ADR-0006 places duties on verification (rules 3.2, 4.3), reasoning (rule 2.2 abstention) and interface (rule 4.2).
  These need PMO REQs to those departments.
- Charters citing ADR-0005 or the civil scope (e.g. `departments/corpus/CHARTER.md` "v1 scope (ADR-0005)") and REQ
  `depends_on: [ADR-0005]` entries were not edited: they belong to departments and PMO.
- Victim / incidental civil plaintiff role: deferred, as recommended in §7.
