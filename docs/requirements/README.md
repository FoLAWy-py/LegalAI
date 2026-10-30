---
id: REQ-INDEX
owner: architecture
status: active
updated: 2026-10-30
---

# Requirements

How departments ask each other for work. Protocol rules: `docs/ORGANIZATION.md` §5.
Template: `docs/templates/REQ.md`.

## Naming

`REQ-<FROM>-<NNNN>-<slug>.md`, where `<FROM>` is the issuing department in uppercase
(`ARCH`, `CASEFILE`, `CORPUS`, `RETRIEVAL`, `REASONING`, `VERIFICATION`, `EVALUATION`, `INTERFACE`, `PMO`)
and `<NNNN>` is the next number within that prefix.

## Lifecycle

```
draft ──► open ──► accepted ──► in-progress ──► delivered ──► verified ──► closed
             └──► rejected (with reason in §7)
```

| Transition | Who | Condition |
|---|---|---|
| draft → open | issuer | §1–§6 complete, acceptance criteria testable |
| open → accepted / rejected | receiver | §7 filled |
| accepted → in-progress | receiver | work started |
| in-progress → delivered | receiver | §8 filled, `scripts/check_all.py` green |
| delivered → verified | **issuer** | every acceptance criterion checked |
| verified → closed | Program Office | nothing left to do |

## Index

| ID | Title | From → To | Status | Wave |
|---|---|---|---|---|
| REQ-PMO-0005 | Synthetic outline set, golden-set spec, eval runner | pmo → evaluation | open | 1 |
| REQ-PMO-0001 | Case document intake and CaseFileStore | pmo → casefile | open | 1 |
| REQ-PMO-0002 | Origins assessment and v1 CN criminal law | pmo → corpus | open | 1 |
| REQ-PMO-0004 | Outline verification (deterministic, then model) | pmo → verification | open | 1 |
| REQ-PMO-0003 | Law and case-file retrieval | pmo → retrieval | open | 1 |
| REQ-ARCH-0001 | Agent framework spike for ADR-0002 | architecture → reasoning | open | 2 (needs PMO-0005 synthetic set) |
| REQ-PMO-0006 | Outline pipeline, config, CLI | pmo → interface | open | 2 |
| REQ-PMO-0007 | Re-scope v1 to CN criminal cases (ADR-0006, PROJECT, contracts 0.3.0) | pmo → architecture | delivered | 1 (contracts serialized) |
| REQ-PMO-0011 | Manual-import path; delete 9 NPC files; 403 is final | pmo → corpus | open | 2 (with PMO-0002 resumption) |
| REQ-PMO-0008 | CN financial-crime pilot dataset from SPP Guiding Case 175 | pmo → evaluation | draft | 2 (needs PMO-0002, PMO-0005, PMO-0007) |

Wave 1 REQs touch disjoint departments and can be dispatched to subagents in parallel, each working against
`ZZ` fakes. Wave 2 starts when its dependencies are delivered.
