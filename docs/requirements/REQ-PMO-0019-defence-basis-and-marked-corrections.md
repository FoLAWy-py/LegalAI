---
id: REQ-PMO-0019
title: Cite the law behind each defence, and carry marked look-alike corrections in contracts
from: pmo
to: architecture
owner: pmo
status: open
priority: P1
created: 2026-10-31
updated: 2026-10-31
depends_on: [ADR-0006, ADR-0007, REQ-PMO-0009]
---

# REQ-PMO-0019: Cite the law behind each defence, and carry marked look-alike corrections in contracts

## 1. Context
Project owner decisions (2026-10-31, to PMO):
1. **Defences:** "I'm fine with this approach, but the outline must also include citations to the relevant legal
   provisions supporting each defence." The owner accepts ADR-0006 §4 (a defence shown as `contradicts` links on the
   elements it would negate) and **requires** the law behind each defence to be cited. This fires ADR-0006 §4.4's
   revisit trigger (Option C).
2. **Look-alike characters:** "Look-alike characters can be corrected, but every correction must be clearly marked and
   traceable to the original text." This confirms casefile's mapping (REQ-PMO-0009) and its narrow charter amendment.
   Today the corrections are recorded only inside casefile's store (`meta.json`). Contracts carry nothing, so
   verification, reasoning and interface cannot see or mark a corrected character in a quote.

## 2. Requirement
All changes MUST be additive: a minor bump; nothing removed, renamed or tightened; existing tests in every department
unchanged.
1. **Defence legal basis:**
   - Contracts MUST let an outline state each raised defence or justification once, with: a description; one or
     more **law** citations establishing it (law sources only, as for `Element.legal_basis`); and the ids of the
     elements it would negate.
   - Each `contradicts` link that supports a defence MUST be able to reference that defence.
   - A defence with no law citation, or with links pointing to an unknown defence, MUST NOT validate.
   - The rule of ADR-0006 §4.3 stays: a link's `purpose` states facts only. The defence's legal rule lives in its
     cited basis.
2. **Marked corrections:**
   - `CaseDocument` (and `SourceDocument`, for corpus's opt-in mapping) MUST be able to carry the list of code-point
     corrections: offset, original code point, replacement, mapping id and version.
   - Contracts MUST provide a deterministic way to tell, for any span, which corrections fall inside it, so a
     consumer can mark them and rebuild the original text of that span.
   - Absence of the field means "no corrections were made", never "unknown". State this in the docstring.
3. Record the decisions in a new ADR that supersedes ADR-0006 §4 (or amends it per STD-DOC §4). Cover:
   - how a defence relates to elements and to gaps;
   - the **marking duty**: any rendering of a quote that contains a corrected character MUST mark it and make the
     original code point available.
4. List the adoption work for each department in §8, so PMO can issue REQs: casefile/corpus populate corrections;
   reasoning emits defences; verification checks defence bases; interface renders defences with their law and marks
   corrections. Edit no department code.

## 3. Interface
`EvidenceOutline`, `EvidenceLink`, `CaseDocument`, `SourceDocument`, possibly `SourceSpan`/`Citation` helpers.

## 4. Acceptance criteria
1. A contract test builds a valid criminal outline on `ZZ` data with one defence citing law, two `contradicts` links
   referencing it, and the elements it negates. Negative tests: a defence without law, a link to an unknown defence, and
   a defence citing a case file as its basis.
2. A contract test builds a `CaseDocument` with corrections, selects the corrections inside a span, and rebuilds the
   span's original text exactly. Documents without the field still validate.
3. The new or amended ADR is accepted and records both owner decisions and the marking duty.
4. `CONTRACT_VERSION` minor bump; `scripts/check_all.py` passes with every existing test unchanged.

## 5. Out of scope
Department adoption (separate REQs); the incidental civil action (ADR-0006 §2.2).

## 6. Open questions
- Should a defence also be allowed to have its own gap (e.g. "defence raised, but no evidence for it")? Architecture
  recommends; owner decides if it changes what the outline means.

## 7. Response
_Pending (architecture)._

## 8. Delivery
_Pending (architecture)._
