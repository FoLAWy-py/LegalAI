---
id: ADR-0003
title: Local deployment with DeepSeek via DeepInfra as the model provider
owner: architecture
status: accepted
deciders: [project owner]
updated: 2026-10-30
---

# ADR-0003: Local deployment with DeepSeek via DeepInfra as the model provider

## Context
Project owner decision (2026-10-30, D4): the application runs locally; model inference uses
`deepseek-ai/DeepSeek-V4.1-Flash-1017` hosted on DeepInfra.

## Decision
1. **Deployment:** all application code, indexes, source documents, case materials and traces live on
   the local machine under `LEGALAI_DATA_DIR`. No other remote service is used without a new ADR.
2. **Provider:** DeepInfra's OpenAI-compatible endpoint (`LLM_BASE_URL`), model `LLM_MODEL`.
   It is the only approved model provider (P9).
3. **Configuration:** read from environment (`.env`, template `.env.example`) **only by `interface`**,
   which passes typed config objects into reasoning and verification. No other department reads env vars.
4. **Model-agnostic code:** reasoning and verification access models through an OpenAI-compatible
   client behind their own adapter; the model id is configuration, never hard-coded.
5. **Verification independence (P2):** with a single provider, independence comes from (a) deterministic
   checks run first and decisive on failure, (b) separate prompts and code, (c) `VERIFICATION_LLM_MODEL`,
   which can be set to a different model when one is approved.

## Consequences
- **Confidentiality (P9):** prompts — including excerpts of case materials — leave the machine and are
  processed by DeepInfra. Users must be told this; the owner accepts it for v1. Send only the minimum excerpts needed.
- The model id was supplied by the owner and has not yet been verified against the provider. The first live
  test (`@pytest.mark.live`) in reasoning MUST confirm the model responds and supports structured (JSON) output.
- ADR-0002 candidates are limited to frameworks that work with OpenAI-compatible endpoints.

## Validation
Live smoke test passes; eval runs record model id and provider in every `ModelTrace`.
