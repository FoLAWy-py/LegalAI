---
id: SPEC-EVALUATION-GOLDEN-SET
owner: evaluation
status: active
updated: 2026-10-30
---

# Golden-set specification: real evidence outlines (CN criminal first, US stub)

Normative for every real (non-`ZZ`) golden set that evaluation uses to gate a release. It implements
REQ-PMO-0005 §2.2 and is the item format REQ-PMO-0008 (SPP 检例第175号 pilot) builds on. Synthetic `ZZ` data
is a fixture, not a golden set, and is out of scope here.

Binding context: P1, P3, P5, P6, P9 (`docs/PRINCIPLES.md`); ADR-0004 (original language is authoritative);
ADR-0006 (criminal outlines, financial-crime focus, defences as contradicting links, one `as_of`);
REQ-PMO-0002 §2.1 (origin approval rule); evaluation charter (reviewed golden data, reproducible runs).

This spec states no rule of any real legal system. Where it names documents or sections, it names them
as artefacts to capture, not as statements of law.

## 1. Terms

| Term | Meaning |
|---|---|
| Golden set | A versioned collection of items, with its source captures, used to gate a release. |
| Item | One query plus its expected outcome: an expected `EvidenceOutline`, or an expected abstention. |
| Capture | The raw bytes of one official web page or file, as served, plus its capture record. |
| Authority tier | `official` (published by the issuing body on an approved origin) or `secondary` (anything else). |
| Proxy case file | An official public text that recites the evidence of a case, used in place of the confidential dossier (§4). |
| Annotation | A per-target statement about an item: its expected element, link, gap, label or adversarial claim. |
| Drafter | The person (or department agent) who first writes an annotation. |
| Reviewer | A qualified human (§6) who checks annotations against the captured text and approves or rejects them. |

## 2. Storage layout

Golden data lives under `<LEGALAI_DATA_DIR>/evaluation/golden/<set_id>/<version>/` (git-ignored; only this spec
and the loader are in the repository):

```
manifest.json                 # set metadata, item list, capture list, fingerprint (§8)
captures/<capture_id>/raw.<ext>   # bytes exactly as served
captures/<capture_id>/capture.json
captures/<capture_id>/text.txt    # mechanically derived text (§3 S3)
items/<item_id>.json          # §5
reviews/<item_id>/<n>.json    # one file per review event (§7)
CHANGELOG.md
```

Reviewer identities are held in `reviewers.json` next to `manifest.json`, keyed by a stable pseudonymous
`reviewer_id`. Items and reviews reference only `reviewer_id`.

## 3. Source capture and fidelity rules

S1. Every source text MUST be captured byte-faithfully from the **official rendering**: the HTTP response body
    (HTML, PDF, or other file) as served by the origin. Copying from a browser, re-typing, summarising,
    "public text extracts", OCR and mirrors MUST NOT be used.

S2. `capture.json` MUST record: `capture_id`; `requested_url`; `final_url` (after redirects); `retrieved_at`
    (UTC, ISO 8601); `http_status`; `content_type`; `byte_length`; `raw_sha256`; `origin` (the origin entry in
    `departments/corpus/docs/origins.md` and its approval status under REQ-PMO-0002 §2.1); `issuer` (the body
    that published the document, as stated on the page); `authority_tier`.

S3. `text.txt` MUST be derived from `raw.*` by a deterministic, versioned extraction recipe. `capture.json`
    records `recipe_id`, `recipe_version`, `text_sha256`, and, where only part of the page is the document, the
    character range of that portion with the rule that selects it (for example "the element with id X").
    Re-running the recipe on the raw bytes MUST reproduce `text_sha256` exactly.

S4. The portion used by items MUST be checked against the raw bytes by an **independent extraction path** (a
    second extractor, or a reviewer's diff against the raw HTML) before any item citing it is approved. The
    result and its method are recorded in `capture.json` (`independent_check`).

S5. The recipe MUST NOT normalise legal wording: no spelling or punctuation fixes, no full-width/half-width
    conversion, no traditional/simplified conversion, no whitespace changes beyond rules documented in the
    recipe and applied identically on every run.

S6. Every captured document MUST carry an `authority_tier`:
    - `official`: published by the issuing body itself on an origin approved under REQ-PMO-0002 §2.1.
    - `secondary`: everything else, including mirrors, news reports, law-firm pages, aggregators and
      commercial databases, even when the text appears identical.

S7. A `secondary` source MUST NOT support a `SUPPORTED` label, MUST NOT be an element `legal_basis`, and MUST
    NOT be the only support of an expected evidence link. It MAY be stored as context and flagged as such.

S8. Element legal bases MUST cite law served by corpus's `SourceStore` (`doc_id@version_id`, `official` tier).
    `version_id` identifies the **legal version** (as published by the issuer, with `effective_from` /
    `effective_to` taken from the official source), never the retrieval date. Retrieval is tracked by
    `capture_id`.

S9. Every annotation quote MUST occur verbatim in the captured text at its recorded offsets:
    `text[start:end] == span.text` and `quote in span.text`. This is checked automatically (§8 A3); a single
    failure rejects the item.

S10. At each dataset release, captures MUST be re-fetched. If `raw_sha256` changed, every item citing the capture
     is moved to `frozen` (§7) until a reviewer re-approves it against the new capture.

S11. Items MUST be within the practice-area scope of the ADR in force when they are admitted. For v1 that is
     CN criminal cases with a financial-crime focus (ADR-0006 §6.1).

## 4. Case files for criminal items

C1. Real case dossiers (卷宗) are confidential (P9) and MUST NOT be used as golden data.

C2. A **proxy case file** is an `official`-tier public text that recites the evidence of a case: for example the
    facts and the evidence-and-proof sections of a guiding case (such as 基本案情 and 指控和证明犯罪 in an SPP
    guiding case), or a judgment from an approved origin. It is ingested through casefile intake as a
    `CaseDocument` (REQ-PMO-0008 §3) with the item's `case_id`, from the same capture (S1–S4).

C3. An evidence link on a proxy case file cites the **recital**: the passage in which the issuer names an
    item of evidence and states what it shows. The quote is verbatim from that passage. The link `purpose`
    states only what the recital says the evidence shows, as fact (ADR-0006 §4.3). It MUST NOT assert what the
    underlying evidence says beyond the recital.

C4. Each link annotation records `evidence_type` as named in the recital (for example 证人证言, 书证, 鉴定意见,
    电子数据, 审计报告) and `recited_by` (the issuing court or procuratorate).

C5. `relation` is `supports` when the recital presents the evidence as proving the element, and `contradicts`
    when the recital reports evidence or defence submissions (辩护意见) that bear against the element. Defences
    are never elements of their own (ADR-0006 §4.1).

C6. The issuer's own legal reasoning in the proxy text (for example its findings on which provision applies) is
    not evidence and MUST NOT be cited as an evidence link. It MAY be cited as the source for an annotation's
    `rationale`, and it is the reference for the expected charge per defendant group (§5).

C7. A guiding case is used **only** as a proxy case file in v1. It is not an element `legal_basis` until corpus
    ingests case law (REQ-PMO-0002 §5).

C8. Reviewer-written fictional case files combined with real law are **not** allowed in v1 (open question §11).

## 5. Item format

`items/<item_id>.json` holds one JSON object:

| Field | Required | Content |
|---|---|---|
| `item_id` | yes | Stable id, `<set_id>-<NNN>`. Never reused. |
| `added_in` | yes | Set version that first contained the item. |
| `practice_area` | yes | `cn-criminal-financial` or `cn-criminal-other` (v1). |
| `query` | yes | A contract-valid `LegalQuery`: `jurisdiction` `CN`, `task_type` `evidence_outline`, `case_id`, `party_role` (`prosecution` or `defendant`), `response_language`, `as_of`. |
| `query_language` | yes | BCP 47 tag of `query.text` (breakdown key, ADR-0004). |
| `defendant_group` | if several | Label of the defendant group the outline is about, with the source span that defines it. One item per group and charge. |
| `charge` | yes | The charged offence for this group as stated in the proxy text, with its citation; copied into `expected.cause_of_action`. |
| `reference_date` | yes | `{basis: conduct \| judgment \| other, date, citation, note}`. Which date governs is a legal question and MUST be cited from the source, never assumed (ADR-0006 §6.2). If elements would need law from more than one reference date, the item expects abstention or a flag. |
| `expected` | yes | A contract-valid `EvidenceOutline` (or an abstaining one with `abstain_reason`). |
| `expected_abstention_reason` | if abstaining | One of: `no_applicable_provision`, `out_of_scope`, `mixed_reference_dates`, `insufficient_sources`, plus free text. |
| `annotations` | yes | One per element, link and gap of `expected`: `{target_id, rationale, rationale_citation, evidence_type?, recited_by?}`. |
| `verification_labels` | yes | Expected verifier verdict per element and link (`supported`, `unsupported`, `contradicted`, ...), each with the citation that decides it. |
| `adversarial_claims` | no | False statements for the verifier, e.g. a wrong charge for a defendant group: `{claim_id, text, expected_verdict, citation}`. |
| `provenance` | yes | `drafted_by`, `drafted_at`, `drafting_method` (`manual` or `model_assisted` with model id, prompt id and version). |
| `review_status` | yes | §7 state. |
| `reviews` | derived | Paths of review records (§7). |

Rules on content:

I1. `expected` MUST pass `EvidenceOutline` validation and follow ADR-0006: defences as `contradicts` links;
    purposes factual; `burden_on` set only if the element's own cited `legal_basis` states the burden; one
    `as_of`.

I2. Every element of the charged offence appears, with a supporting link or a gap. A gap is expected where the
    proxy text does not recite evidence for the element, or recites only contradicting evidence.

I3. When defendant groups receive different charges because one element (for example the intent element) is
    proved for one group and not another, each group is a separate item, and the unproved element carries a gap
    in that group's item.

## 6. Reviewer qualification

R1. Only a human reviewer may approve an item. Department agents and models may draft; they never review.

R2. Proposed qualifications for **CN** items (pending the project owner's decision, REQ-PMO-0005 §6):
    a PRC practising lawyer with criminal-defence or criminal-litigation experience, a serving or former judge or
    procurator with criminal-case experience, or a law academic specialising in criminal law and criminal
    procedure. The project owner names and approves each reviewer.

R3. Each reviewer record in `reviewers.json` holds: `reviewer_id`; `qualification_type`;
    `qualification_jurisdiction`; `issuing_body`; `credential_ref` (a reference or a hash of the credential
    number, never the raw number in reports); `verified_by` and `verified_at` (who checked the qualification);
    `approved_by_owner_at`; `conflicts` (declared conflicts of interest).

R4. Every review record (`reviews/<item_id>/<n>.json`) holds: `reviewer_id`, `reviewed_at`, the capture ids and
    hashes reviewed against, a decision per annotation target (`approve`, `reject`, `amend` with the amendment),
    and comments.

R5. The approving reviewer MUST NOT be the drafter. Model-assisted items need two approving reviewers.

R6. Named reviewers: **CN: TBD. US: TBD.** Until a reviewer is named, no item can leave `pending` (§7) and no
    real golden set can gate a release.

## 7. Review workflow

| State | Meaning | Next |
|---|---|---|
| `draft` | Being written; automated checks may fail. | `pending` |
| `pending` | All §8 automated checks pass; awaiting review. | `approved`, `rejected`, `disputed` |
| `disputed` | Reviewers disagree, or a reviewer amended a target. | `pending` (after amendment), `rejected` |
| `approved` | Approved by the required number of qualified reviewers (R5). | `frozen`, `retired` |
| `frozen` | A cited capture or law version changed (S10), or a defect was reported. | `pending` |
| `rejected` / `retired` | Not used. Kept for audit. | — |

W1. Model output is never accepted as is. A model-assisted annotation is a proposal that a reviewer checks
    against the captured text, target by target.

W2. Labels such as `supported` have no effect before `approved`. A set with any non-`approved` item can be run
    for diagnostics, but the runner MUST NOT report a release-gate verdict on it.

W3. Every state change is a review record (R4), so the history of every item can be audited.

## 8. Automated admission checks (loader; any failure rejects the item)

The golden-set loader that enforces these checks, and W2, is built with the first real set (REQ-PMO-0008).
Until then, no real set exists and none can gate a release.

| Check | Rule |
|---|---|
| A1 | `sha256(raw) == raw_sha256` for every capture. |
| A2 | Re-running the recipe reproduces `text_sha256` (S3); `independent_check` recorded (S4). |
| A3 | Every quote: `text[start:end] == span.text` and `quote in span.text` (S9). |
| A4 | `query` and `expected` pass contract validation; `expected.query == query`. |
| A5 | Every law citation resolves in corpus's `SourceStore`, `official` tier, version in force on `as_of`, jurisdiction `CN`. |
| A6 | No `secondary` capture supports a `supported` label, a legal basis or the only support of a link (S7). |
| A7 | `version_id` values are legal versions, not retrieval dates (S8). |
| A8 | ADR-0006 rules (I1); one item per defendant group and charge (I3). |
| A9 | `approved` items have the review records R4/R5 require, with reviewers in `reviewers.json` approved by the owner. |
| A10 | Practice area within scope (S11). |

## 9. Versioning

V1. Set versions use semver: MAJOR for item-format changes, MINOR for added items, PATCH for corrections.

V2. A released version is immutable. Any change, including a single quote fix, is a new version with a
    `CHANGELOG.md` entry naming the items affected and why.

V3. The manifest records a SHA-256 fingerprint over the canonical JSON of all items, capture records and
    reviewer approvals. Every eval report pins `dataset_id`, `version` and fingerprint (runner behaviour,
    `EvalReport.dataset_fingerprint`).

V4. When corpus ingests a new legal version of a document cited by an item, the item moves to `frozen` and is
    re-reviewed for its `as_of`.

## 10. Lessons from the owner-supplied yu-huan pilot (non-normative)

The PMO check on 2026-10-30 found the pilot internally consistent (hashes, offsets) but not golden data.
Each finding maps to a rule above:

| Finding | Rule that prevents it |
|---|---|
| Document labelled as an official capture was a "public text extract" that differed from the official page. | S1, S3, S4, A2 |
| Three documents were secondary mirrors, while annotations relied on them. | S6, S7, A6 |
| `version_id` was the retrieval date. | S8, A7 |
| Labels were `SUPPORTED` while review was pending and no reviewer was recorded. | W2, R1, R6, A9 |
| Files carried no recorded extraction recipe or independent check. | S3, S4 |
| At the time, the case was outside the v1 practice area. | S11, A10 |

## 11. US section (stub)

US golden sets are deferred (ADR-0006 §6.3; D7/D8 re-opened). When a US REQ is issued, this section will add:
approved US origins, US proxy case files (for example published opinions that recite the record), the reviewer
qualification (for example admission to a US bar with criminal practice), and US citation display rules. All
rules in §3–§9 apply unchanged unless that section says otherwise.

## 12. Open questions

1. Named CN and US reviewers and their qualification criteria (project owner; REQ-PMO-0005 §6, REQ-PMO-0008 §6).
2. Whether reviewer-written fictional case files may be combined with real CN law (C8), and if so how they are
   marked. This needs architecture to amend `docs/standards/legal-content.md` §1/§4.
3. Whether golden law captures should be shared with corpus's store, or whether evaluation keeps its own
   captures and corpus keeps its own. Either way, A5 requires the corpus version to match the captured text.
