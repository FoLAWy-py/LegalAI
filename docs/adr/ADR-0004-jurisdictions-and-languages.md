---
id: ADR-0004
title: v1 jurisdictions (US, CN) and multi-language handling
owner: architecture
status: accepted
deciders: [project owner]
updated: 2026-10-30
---

# ADR-0004: v1 jurisdictions (US, CN) and multi-language handling

## Context
Project owner decision (2026-10-30, D1): v1 covers the United States and China, multi-language.
Legal meaning depends on exact wording, so language handling is a reliability issue (P1).

## Decision
1. Jurisdiction codes: `US` (federal), `US-XX` (states), `CN` (national). Further scope (which states,
   local regulations) is set per use case in `docs/PROJECT.md`.
2. **Original text is authoritative.** Sources are stored, cited and quoted only in their original
   language. Quotes in a `Citation` are always original-language text.
3. **Translations are derivatives.** A translation may be shown to help the reader, but it is labelled
   as a machine or human translation, is never cited as a source, and is never used to verify a claim.
4. **Answer language** follows the user's request; claims may be written in that language while their
   citations stay in the source language.
5. **Cross-lingual retrieval** is required: a query in Chinese can retrieve US sources and vice versa,
   but results are still filtered by the query's jurisdiction.
6. Legal terms do not map one-to-one between systems (e.g. common-law and civil-law concepts). Reasoning
   MUST NOT treat a US concept and a CN concept as equivalent without saying so.

## Consequences
- Contracts: `LegalQuery` needs a response-language field (REQ to architecture when the use case contracts are defined).
- Evaluation needs golden sets in both languages and cross-lingual cases.
- Verification checks entailment against original-language text.

## Validation
Evaluation reports metrics broken down by jurisdiction and by query language.
