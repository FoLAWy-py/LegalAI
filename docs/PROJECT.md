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
| D2 | First use case | Evidence outline: proof chart with gap analysis | ADR-0006 (was ADR-0005) |
| D3 | Source origins and licensing | Public sources, downloaded locally and kept for private local use only. Automated fetching is approved for official sites with no robots policy (court.gov.cn, csrc.gov.cn, spp.gov.cn). Sites that forbid or refuse bots are not circumvented; their documents come in by manual import (2026-10-30) | REQ-PMO-0002 §7; REQ-PMO-0011 |
| D4 | Deployment and model provider | Local; `deepseek-ai/DeepSeek-V4.1-Flash-1017` on DeepInfra | ADR-0003 |
| D5 | Agent framework | Open — decided by spike REQ-ARCH-0001 | ADR-0002 |
| D6 | Practice area | **Criminal cases**, with **financial crimes** as the v1 focus (revised 2026-10-30; replaces civil contract disputes) | ADR-0006 |
| D7 | US law layer | **Deferred**: re-opened for the criminal context; decided before any US REQ (earlier answer "federal + one state" was for civil disputes) | ADR-0006 |
| D8 | Which US state | **Deferred**: re-opened together with D7 | ADR-0006 |
| D9 | Input formats | Digital documents only (no OCR) | ADR-0006 (was ADR-0005) |
| D10 | Sequencing | CN first; US law only after the CN vertical slice is confirmed end to end (2026-10-30) | ADR-0006 |
| D11 | v1 pilot case | SPP 检例第175号, selected by the Program Office; private local copy only (2026-10-30) | ADR-0006; REQ-PMO-0008 |
| D12 | Historical law versions | No constructed consolidations; original 1997 text and amendment acts are stored and cited separately (2026-10-30) | REQ-PMO-0002 §7 |
| D13 | Access control | Never get past a site's refusal or block (UA, headers, IP, timing); the 9 NPC files obtained that way are deleted (2026-10-30) | REQ-PMO-0002 §7 |

## Roadmap (phase gates)
1. **Foundation** — contracts v0.2, boundaries, standards, v1 decisions (done 2026-10-30).
2. **Spike** — REQ-ARCH-0001 on synthetic `ZZ` data; ADR-0002 decided.
3. **Vertical slice** — evidence outline for a charged offence, **CN criminal first** (financial crimes; pilot SPP 检例第175号),
   end-to-end with verification and eval gate.
   US follows only after the CN slice is confirmed end to end and D7/D8 are re-decided.
4. **Hardening** — larger golden set, adversarial tests, temporal edge cases, human review loop.
