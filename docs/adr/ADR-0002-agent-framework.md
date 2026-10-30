---
id: ADR-0002
title: Agent framework for the reasoning harness
owner: architecture
status: proposed
deciders: [project owner]
updated: 2026-10-30
---

# ADR-0002: Agent framework for the reasoning harness

## Context
`reasoning` needs an agent harness: model calls, tool use (search, fetch span), structured outputs,
traces. Reliability matters more than autonomy (P7). The framework choice is confined to the
`reasoning` department; no other department may depend on it.

## Options considered
| Option | Pros | Cons | Reliability impact |
|---|---|---|---|
| ~~Claude Agent SDK~~ | — | Built around Claude models; excluded by ADR-0003 (DeepSeek via DeepInfra) | — |
| Own loop over the `openai` SDK (OpenAI-compatible endpoint) | Full control, minimal surface, easy to trace | More code to own | Good: every step explicit |
| LangGraph | Explicit state graph, checkpoints, replay | Extra abstraction layer, dependency weight | Good for deterministic workflows |
| Pydantic AI | Typed outputs, model-agnostic | Younger ecosystem | Good for structured output validation |

## Proposed decision (pending spike REQ-ARCH-0001)
1. **Pipeline first:** the outer flow (understand query → retrieve → draft → hand to verification)
   is plain, deterministic Python owned by `reasoning`. Agent loops run only inside bounded steps
   with a max-turn limit and a tool allow-list.
2. **Model access behind one adapter** inside `reasoning`, so every call records a `ModelTrace` and the
   framework or model can be swapped without touching other departments.
3. Candidate frameworks are compared in a spike on the same golden set; the winner is chosen on
   citation validity and claim support rate first, latency/cost second.
4. Model: configured per ADR-0003 (`LLM_MODEL`, currently DeepSeek via DeepInfra). Candidates MUST work with an
   OpenAI-compatible endpoint and MUST NOT rely on provider-specific features without a fallback.

## Consequences
- `reasoning` must deliver the adapter and the spike results before building use cases.
- `evaluation` must provide a small golden set (REQ to be issued once the first use case and
  jurisdiction are fixed).

## Validation
Spike report in REQ-ARCH-0001 §8; this ADR moves to `accepted` with the chosen option.
