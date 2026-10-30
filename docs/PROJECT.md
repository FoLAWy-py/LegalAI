---
id: PROJECT
owner: architecture
status: draft
updated: 2026-10-30
---

# Project Brief

## Goal
Build a reliable, auditable harness for legal AI tasks, where every legal statement can be traced
to an exact, versioned source and every answer is independently verified before delivery.

## Non-goals (for now)
- Giving legal advice to end users without professional review.
- Actions with external effect (filing, sending, signing).

## Open decisions (project owner)
These block specific REQs. Record answers here and in an ADR where they bind several departments.

| # | Decision | Answer (2026-10-30) | Record |
|---|---|---|---|
| D1 | Target jurisdiction(s) and language(s) | US and CN, multi-language | ADR-0004 |
| D2 | First use case | Evidence outline: proof chart with gap analysis | ADR-0005 |
| D3 | Source origins and licensing | Public sources, downloaded locally | corpus CHARTER |
| D4 | Deployment and model provider | Local; `deepseek-ai/DeepSeek-V4.1-Flash-1017` on DeepInfra | ADR-0003 |
| D5 | Agent framework | Open — decided by spike REQ-ARCH-0001 | ADR-0002 |
| D6 | Practice area | Civil contract disputes | ADR-0005 |
| D7 | US law layer | Federal + one state | ADR-0005 |
| D8 | Which US state | **Open — project owner to choose** | — |
| D9 | Input formats | Digital documents only (no OCR) | ADR-0005 |

## Roadmap (phase gates)
1. **Foundation** — contracts v0.2, boundaries, standards, v1 decisions (done 2026-10-30).
2. **Spike** — REQ-ARCH-0001 on synthetic `ZZ` data; ADR-0002 decided.
3. **Vertical slice** — evidence outline for contract disputes, CN first, then US (after D8), end-to-end with verification and eval gate.
4. **Hardening** — larger golden set, adversarial tests, temporal edge cases, human review loop.
