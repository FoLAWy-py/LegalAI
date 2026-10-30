---
id: REQ-PMO-0008
title: Build the CN financial-crime pilot dataset from SPP Guiding Case 175
from: pmo
to: evaluation
owner: pmo
status: draft
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [REQ-PMO-0002, REQ-PMO-0005, REQ-PMO-0007]
---

# REQ-PMO-0008: Build the CN financial-crime pilot dataset from SPP Guiding Case 175

## 1. Context
The project owner asked PMO (2026-10-30) to choose a suitable real case and set v1 to **financial crimes**.
The owner-supplied Yu Huan pilot fails source fidelity (REQ-PMO-0005 §1).

PMO selected **最高人民检察院 检例第175号 张业强等人非法集资案** (SPP 44th batch of guiding cases, published 2023-06-13,
official page https://www.spp.gov.cn/spp/jczdal/202306/t20230613_617294.shtml). Reasons:
- It is the issuing body's own publication.
- It is a financial crime: private-fund illegal fundraising.
- The case text has a section on charging and proving the crime (指控和证明犯罪) that maps evidence to each element
  (公开性, 利诱性, 社会性, 非法占有目的). The evidence includes promotional material, investor and staff testimony,
  buy-back agreements, fund-flow audits and personal-spending records. This is what an evidence outline does.
- Some defendants were convicted of 集资诈骗 and others of 非法吸收公众存款, depending on whether each had the intent
  to take the funds (非法占有目的). So element-level distinctions matter.
- It tests temporal validity: the conduct ran from 2014 to 2018 and the judgments came in 2021, while the cited
  interpretation 法释〔2022〕5号 came later. Which version applied when must come from corpus (P4), never from memory.

A superseded draft of this REQ selected SPC Guiding Case 270 (drunk driving). It was replaced when the owner set the
financial-crime focus.

Limitation: a guiding case is an edited summary, not the case dossier. Its 基本案情 and 指控和证明犯罪 sections serve
as proxy case files. The pilot tests law grounding, evidence-to-element mapping and verification, not intake of real
evidence documents.

## 2. Requirement
1. Capture the official page byte-faithfully: raw HTML, retrieval time, URL, sha256. Derive the 检例第175号 text from the
   raw HTML mechanically, without retyping. spp.gov.cn is approved (REQ-PMO-0002 §7, PMO decisions 2026-10-30) for a **private local copy only**: kept
   under the data dir, never committed, published or redistributed (project owner decision, 2026-10-30).
2. Store it under `<data_dir>/evaluation/cn-spp175-pilot/` with a manifest, in the shape the golden-set spec
   (REQ-PMO-0005) defines.
3. Draft annotations with exact offsets, each marked `review_status: pending`:
   - the charged offences for each defendant group;
   - elements of each offence;
   - evidence links per element;
   - gaps and contested-evidence items;
   - adversarial false claims, e.g. "all defendants were convicted of 集资诈骗".
   Annotations are drafted from the source text by the evaluation department; model output alone is not acceptable.
4. A qualified reviewer named by the project owner reviews every item before the set may gate a release.

## 3. Interface
Golden-set item format (REQ-PMO-0005); `CaseDocument` via casefile intake for the proxy case file.

## 4. Acceptance criteria
1. The stored text's hash matches the manifest, and the text equals the 检例第175号 portion of the raw official HTML,
   checked by an independent extraction path.
2. Every annotation quote occurs verbatim at its offsets (automated check).
3. Every element's legal basis resolves to a corpus document whose version was in force on the relevant date
   (conduct period or judgment date, as the annotation states).
4. Review status and reviewer are recorded per item; no item is marked reviewed without a named reviewer.

## 5. Out of scope
The underlying full judgments (not on an approved origin), and US cases.

## 6. Open questions
- Reviewer identity and qualification (project owner).

## 7. Response
_Pending (evaluation)._

## 8. Delivery
_Pending (evaluation)._
