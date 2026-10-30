---
id: REQ-PMO-0006
title: Wire the outline pipeline, configuration and CLI
from: pmo
to: interface
owner: pmo
status: open
priority: P2
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0003, ADR-0005]
---

# REQ-PMO-0006: Wire the outline pipeline, configuration and CLI

## 1. Context
Interface is the composition root and the last gate before the user (P3, P8, P9).

## 2. Requirement
1. Load configuration from `.env` / environment (keys in `.env.example`) into typed config; fail fast on missing
   or invalid values; never log the API key.
2. `build_pipeline(config)` constructs and injects all ports; usable by evaluation. Until departments deliver,
   it may wire `ZZ` fakes behind an explicit `--synthetic` flag.
3. CLI: ingest a case directory; produce an outline for (`--jurisdiction`, `--as-of`, `--role`, `--lang`, cause
   of action text); render as proof chart or 证据目录 (Markdown).
4. Render only items verified SUPPORTED; elements whose basis failed verification are shown as "unverified —
   withheld" with the reason; gaps always shown. Every output states jurisdiction, as-of date, model, and disclaimer
   that the output is not legal advice and that excerpts were processed by the model provider.

## 3. Interface
Public APIs of all core departments; `EvidenceOutline`, `VerificationReport`.

## 4. Acceptance criteria
1. End-to-end test with `--synthetic` fakes produces both renderings; withheld items never appear as verified.
2. Missing `DEEPINFRA_API_KEY` → clear error before any work; key never appears in logs (log-capture test).
3. Audit log records request, outline and report under `<data_dir>/interface/` (P5, P9).
4. `scripts/check_all.py` passes.

## 5. Out of scope
Web UI, multi-user access.

## 6. Open questions
- None.

## 7. Response
_Pending (interface)._

## 8. Delivery
_Pending (interface)._
