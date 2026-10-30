---
id: CHARTER-INTERFACE
owner: interface
status: active
updated: 2026-10-30
---

# Interface Charter

## Mission
Wire the departments into one pipeline and deliver only verified results to users.

## Owns
- The composition root: constructs `SourceStore`, `CaseFileStore`, `Retriever`, `EvidenceRetriever`,
  `OutlineBuilder`, `Answerer`, `Verifier` and injects them.
- The pipeline: query → answer → verify → render; plus a pipeline factory evaluation can call.
- CLI / API / UI, configuration (`.env`, ADR-0003 — the only department that reads env vars), disclaimer text,
  audit log of requests and reports (per P9).
- Renderings of an `EvidenceOutline`: US-style proof chart and CN-style 证据目录, each showing gaps prominently.

## Does not own
Any legal logic. If interface needs behaviour changed, it files a REQ.

## Interfaces
- **Consumes:** public APIs of casefile, corpus, retrieval, reasoning, verification; all contract types.
- **Provides:** `build_pipeline(...)`, CLI/API entry points.

## Quality bars
- Never displays a claim whose verdict is not `SUPPORTED` unless the user explicitly asks for
  unverified output, and then labels it clearly.
- Every response shows jurisdiction, as-of date, verification status and disclaimer.

## Reliability duties
P3 (the last gate before the user), P8 (human-in-the-loop framing), P9 (confidential logging).
