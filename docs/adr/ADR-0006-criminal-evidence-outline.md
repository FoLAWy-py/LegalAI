---
id: ADR-0006
title: v1 use case — evidence outline (proof chart with gaps) for CN criminal cases
owner: architecture
status: accepted
deciders: [project owner, architecture]
supersedes: [ADR-0005]
updated: 2026-10-30
---

# ADR-0006: v1 use case — evidence outline for CN criminal cases

Supersedes ADR-0005. Every ADR-0005 decision not changed below is carried over here, so this ADR can be read on its
own.

## Context
Project owner decisions, first round (2026-10-30, recorded in ADR-0005): D2 evidence outline as a **proof chart with
gap analysis**; D9 inputs are **digital documents only** (Word, text, PDFs with a text layer; no OCR).

Project owner decisions, revision (2026-10-30, given to the Program Office, REQ-PMO-0007):
- **D6 revised:** the v1 practice area is **criminal cases**. This replaces civil contract disputes. Within criminal
  cases, the v1 focus is **financial crimes**.
- **Pilot:** the v1 pilot case is SPP 检例第175号, selected by the Program Office (REQ-PMO-0008).
- **Sequencing:** CN first. US law is taken up only after the CN vertical slice is confirmed end to end.
- **Origin approval** for corpus is delegated to the Program Office (rule in REQ-PMO-0002 §2.1).

ADR-0005 is accepted, and accepted ADRs are immutable except for status (STD-DOC §4). It is therefore superseded,
not amended. Contracts v0.2 are in use by Wave 1 departments, so the change to them MUST be additive.

Deciders: the project owner made the scope decisions above. Architecture made the representation rules in
"Decision" §3–§5, within that scope.

## Options considered
How to represent defences and justifications raised against a charge:

| Option | Pros | Cons | Reliability impact |
|---|---|---|---|
| **A. `contradicts` links on the offence element(s) they would negate** | Works with contracts v0.2 shapes as they are; matches REQ-PMO-0005 §2.1; a defence appears only where case evidence points to it | A link cites case files only, so the law that sets up the defence is not cited in the outline | Good if a link's `purpose` is barred from stating the defence's legal rule (rule 4.3); the limit is visible and testable |
| B. Defences as their own `Element`s | The defence's legal basis is cited like any element | Without a new field to mark them, a gap on a defence reads as a gap in the charge; outlines fill up with defences nobody raised; Wave 1 work must change | Bad without a new field: it misstates what the prosecution still lacks |
| C. Option B plus a new `Element` kind field | Defences are both cited and kept apart from offence elements | Wider contract change while five departments build against v0.2; meaning not yet tested by evaluation | Possibly best long term; premature now |

## Decision

### 1. What the system produces
Given a case (a set of case files), a jurisdiction, an as-of date, the user's party role and a **charged offence**, the
system produces an `EvidenceOutline` (contract field `cause_of_action` holds the charged offence):

1. **Elements of the offence (犯罪构成)**: what must be proved for the charged offence. Each element cites the
   **law** that establishes it (`Element.legal_basis`, law sources only).
2. **Evidence links**: passages from the **case files** (for example indictment, witness statements, forensic and
   inspection records) mapped to elements. Each has an exact citation (document, page, quote), whether it supports
   or contradicts the element, and its purpose (证明目的).
3. **Gaps**: every element without adequate supporting evidence is listed explicitly. Coverage is total: each
   element ends up with a supporting link or a gap, never silently omitted.

A CN-style evidence list (证据目录) and a proof chart are **renderings** of the same outline (interface).

### 2. Party roles
1. In a criminal outline, `LegalQuery.party_role` is `PROSECUTION` (the party bringing the charge) or `DEFENDANT`
   (the accused). Contracts 0.3.0 add `PartyRole.PROSECUTION`. The elements of the offence are the same whichever
   side the user acts for.
2. A role for the victim or the incidental civil plaintiff is **not** added in v1 (REQ-PMO-0007 §7). The incidental
   civil action (附带民事诉讼) is outside the v1 outline until the project owner decides otherwise by REQ. Until then,
   such a request MUST be abstained on as out of scope, not mapped onto a criminal outline.

### 3. Burden and standard of proof
1. This ADR states **no** rule on who bears the burden of proof or on the standard of proof. Both are legal rules.
   They are taken from the ingested official sources at runtime and cited (P1). They are never asserted from memory,
   from a prompt, or from a default in code.
2. `Element.burden_on` is set only when the element's own cited `legal_basis` states who bears the burden for that
   element; otherwise it is `None`.
3. Any statement of a standard of proof in an outline rendering or an answer is a `LEGAL_RULE` claim and needs a
   citation to an ingested law source like any other rule. If no such source is retrieved, the system abstains on
   that statement.

### 4. Defences and justifications (Option A)
1. A defence or justification is represented as one or more `contradicts` links on each offence element it would
   negate, citing the case-file passage relied on. It is not an element of its own.
2. An element whose only links contradict it is not covered (validator in contracts). It MUST have a gap, normally of
   kind `only_contradicting`. An element with both supporting and contradicting links is covered, and the
   contradicting links MUST still be shown next to the supporting ones in every rendering.
3. A link's `purpose` states what the passage tends to show as a matter of fact. It MUST NOT state the legal
   conditions or legal effect of a defence, because an `EvidenceLink` cannot cite law. Verification treats a legal
   rule inside a `purpose` as an unsupported legal assertion.
4. Revisit trigger: if qualified reviewers or evaluation need the legal basis of defences cited in the outline, a new
   REQ to architecture adds it additively (Option C) under a superseding ADR.

### 5. Two kinds of sources (unchanged from ADR-0005)
| Kind | Owner | Store port | Confidential |
|---|---|---|---|
| Law (statutes, interpretations, cases) | corpus | `SourceStore` | no (public) |
| Case files (indictments, statements, records, pleadings) | casefile | `CaseFileStore` | **yes** (P9) |

Every `SourceSpan` states which kind it points to. Element legal bases MUST cite law; evidence links MUST cite case files.

### 6. Scope for v1
1. **CN (criminal, financial-crime focus):** exactly the scope in REQ-PMO-0002 §2.2, which is authoritative for the
   list and for the version date ranges. In summary:
   - the Criminal Law (刑法) as amended, with its consolidated versions and the amendment acts (修正案) that produced them;
   - the Criminal Procedure Law (刑事诉讼法), the SPC interpretation on applying it, and the official provisions on
     examining and judging evidence and on excluding illegal evidence in criminal cases;
   - the judicial interpretations on illegal fundraising and, as REQ-PMO-0002 §2.2 says, other financial-crime
     interpretations;
   - the non-criminal financial-regulation provisions that the pilot relies on for the illegality element, as named in
     REQ-PMO-0002 §2.2;
   - if its origin is approved, the SPP rules of criminal procedure for procuratorates.

   Exact official titles, document numbers, issuers, versions and effective dates are taken from the official
   sources by corpus, never from this ADR or from memory. No consolidated text is constructed where no official one
   exists. Other civil law (Civil Code, Civil Procedure Law, civil evidence provisions) is no longer v1 scope.
   Financial crimes are the v1 focus for datasets and the pilot. The contracts are not limited to them: a
   non-financial charged offence is a valid outline.
2. **Reference date (known limitation).** An outline is built and verified against the single `LegalQuery.as_of`
   (P4). In criminal cases the conduct and the judgment can fall on different dates, as in the pilot. Which date's
   law governs an element is a legal question. It is answered from the ingested sources and cited, never by this
   ADR or from memory. Contracts 0.3.0 cannot express law from more than one reference date in one outline. When
   that is needed, the outline MUST abstain or flag rather than mix dates silently (P3), until an additive contract
   field is added through a new REQ.
3. **US: deferred.** No US law is ingested for v1. D7 (US law layer) and D8 (which state) are **re-opened** for the
   criminal context and will be decided before a US REQ is issued. ADR-0004 (US and CN jurisdictions, language
   handling) still stands; only the sequencing changes. Copyrighted secondary sources are not ingested.

## Consequences
- Contracts 0.3.0 (additive minor bump over 0.2.0): `PartyRole.PROSECUTION`; docstrings of `PartyRole`, `LegalQuery`,
  `Element`, `EvidenceOutline` and `cause_of_action` cover a charged offence. No field or value is removed or renamed.
  The JSON value `"prosecution"` is new, so consumers that branch on `PartyRole` MUST handle it or fail closed.
- Verification checks law citations against `SourceStore` and evidence citations against `CaseFileStore`. It also
  needs checks for rule 4.3 (no legal rule in a link `purpose`) and rule 3.2 (`burden_on` set only when the cited law
  states it).
- Reasoning abstains on incidental civil action requests (rule 2.2). Interface renders contradicting links next to
  supporting links (rule 4.2).
- The duties above on verification, reasoning and interface take effect through REQs from the Program Office to those
  departments. This ADR does not edit their work.
- Evaluation builds golden criminal outlines for CN, financial crimes first, reviewed by a qualified person
  (REQ-PMO-0005); the pilot is SPP 检例第175号 (REQ-PMO-0008).
- Department charters that cite ADR-0005 or civil contract scope are updated by their owning departments. Their
  REQs' `depends_on` entries are updated by the Program Office.

## Validation
The CN criminal vertical slice passes the release gate on the CN golden set (financial crimes first, including the
SPP 检例第175号 pilot once reviewed), with at least one case where a defence is supported by contradicting evidence.
Revisit §6.2 if the pilot needs element legal bases from more than one reference date. Revisit §4 if reviewers find the uncited legal basis of defences
makes outlines misleading.
