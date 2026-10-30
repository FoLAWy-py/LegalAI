---
id: REQ-PMO-0007
title: Re-scope v1 to CN criminal cases in ADRs, project brief and contracts
from: pmo
to: architecture
owner: pmo
status: open
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0007: Re-scope v1 to CN criminal cases in ADRs, project brief and contracts

## 1. Context
Project owner decisions (2026-10-30), given to the Program Office in session:
- **D6 revised:** the v1 practice area is **criminal cases**, replacing civil contract disputes.
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
_Pending (architecture)._

## 8. Delivery
_Pending (architecture)._
