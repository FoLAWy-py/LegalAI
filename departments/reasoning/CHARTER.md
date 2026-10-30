---
id: CHARTER-REASONING
owner: reasoning
status: active
updated: 2026-10-30
---

# Reasoning Charter (the agent harness)

## Mission
Turn a `LegalQuery` into an `EvidenceOutline` (v1 use case, ADR-0005) or a `DraftAnswer` — every item cited — or a reasoned abstention.

## Owns
- The agent harness (framework per ADR-0002), the single model adapter, prompts and their versions.
- Workflows per task type. v1 evidence outline: (1) identify cause of action, (2) derive elements from retrieved
  law, (3) search case files per element, (4) map evidence with purpose, (5) declare gaps for every uncovered element.
- Tool definitions the agent may call (search via injected `Retriever`, nothing else without an ADR).
- The `OutlineBuilder` and `Answerer` implementations and `ModelTrace` emission.

## Does not own
Retrieval quality (retrieval). Deciding whether claims are correct (verification). Presentation (interface).

## Interfaces
- **Consumes:** `LegalQuery`, `SourceSpan`, ports `Retriever`, `EvidenceRetriever` (injected), model config from interface.
- **Provides:** `OutlineBuilder` (→ `EvidenceOutline`) and `Answerer` (→ `DraftAnswer`) implementations.

## Quality bars
- 100% of outputs pass contract validation (malformed model output → retry within limit → abstain).
- Citations reference only spans returned by the retriever in the same run.
- Elements come only from retrieved law — never from the model's memory of the law.
- Abstains on unanswerable questions in the golden set (rate set by evaluation).

## Reliability duties
P1 (cite only retrieved spans; quotes copied, never retyped), P3 (abstain when evidence is thin),
P5 (`ModelTrace` per call), P7 (bounded loops, structured outputs, temperature 0).
Must not import or imitate verification logic; self-checks are allowed but never replace verification (P2).
