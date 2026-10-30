---
id: REQ-PMO-0008
title: Build the CN criminal pilot dataset from SPC Guiding Case 270
from: pmo
to: evaluation
owner: pmo
status: draft
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [REQ-PMO-0002, REQ-PMO-0005, REQ-PMO-0007]
---

# REQ-PMO-0008: Build the CN criminal pilot dataset from SPC Guiding Case 270

## 1. Context
The project owner asked PMO (2026-10-30) to choose a suitable real case for the CN criminal pilot. The owner-supplied
Yu Huan pilot fails source fidelity (REQ-PMO-0005 §1). Its facts also predate 2021, so the law versions in force for it
are outside the corpus range.

PMO selected **指导性案例270号 成某明危险驾驶案** (SPC 48th batch, published 2026-02-13, official page
https://www.court.gov.cn/zixun/xiangqing/489281.html). Reasons:
- Official SPC publication, so no mirrors are involved.
- Facts from 2022, with two criminal instances and a related administrative case.
- The dispute is about evidence: blood-sample procedure defects and whether the alcohol test opinion can be used.
  This exercises contradicting links, gaps and admissibility.
- Its cited law (刑法 第133条之一; 法释〔2021〕1号 第126条) lies within corpus scope (REQ-PMO-0002).
- It tests temporal validity, because the drunk-driving opinion in force in 2022 differs from the 2023 version.

Limitation: a guiding case is an SPC-edited summary, not the case dossier. Its 基本案情 serves as a proxy case file.
The pilot therefore tests law grounding, fact-to-element mapping and verification, not intake of real evidence documents.

## 2. Requirement
1. Capture the official page byte-faithfully: raw HTML, retrieval time, URL, sha256. Derive the case 270 text from the
   raw HTML mechanically, without retyping.
2. Store it under `<data_dir>/evaluation/cn-gc270-pilot/` with a manifest, in the shape the golden-set spec
   (REQ-PMO-0005) defines.
3. Draft annotations (charged offence, elements, evidence links, gaps, contested-evidence items, adversarial false
   claims) with exact offsets, each marked `review_status: pending`. Annotations are drafted from the source text
   by the evaluation department; model output alone is not acceptable.
4. A qualified reviewer named by the project owner reviews every item before the set may gate a release.

## 3. Interface
Golden-set item format (REQ-PMO-0005); `CaseDocument` via casefile intake for the proxy case file.

## 4. Acceptance criteria
1. The stored text's hash matches the manifest, and the text equals the case 270 portion of the raw official HTML,
   checked by an independent extraction path.
2. Every annotation quote occurs verbatim at its offsets (automated check).
3. Every element's legal basis resolves to a corpus document whose version was in force on the as-of date of the facts.
4. Review status and reviewer are recorded per item; no item is marked reviewed without a named reviewer.

## 5. Out of scope
The underlying full judgments (not on an approved origin), and US cases.

## 6. Open questions
- Reviewer identity and qualification (project owner).

## 7. Response
_Pending (evaluation)._

## 8. Delivery
_Pending (evaluation)._
