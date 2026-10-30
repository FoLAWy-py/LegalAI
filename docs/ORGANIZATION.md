---
id: ORGANIZATION
owner: architecture
status: active
updated: 2026-10-30
---

# Organization: Departments, Ownership, Communication

The project is split into **departments**. Each department owns one directory, one Python
package, one charter and one subagent definition. Departments are isolated so that each can be
built by a separate agent in parallel without breaking the others.

## 1. Departments

| Department | Package | Mission (one line) | Subagent |
|---|---|---|---|
| **architecture** | `legalai_contracts` | Owns shared contracts, standards, ADRs. The only shared code. | `architect` |
| **casefile** | `legalai_casefile` | Ingests confidential user case documents with page mapping; `CaseFileStore`. | `casefile` |
| **corpus** | `legalai_corpus` | Acquires, parses, versions and stores legal sources with provenance. | `corpus` |
| **retrieval** | `legalai_retrieval` | Indexes sources and returns the most relevant exact spans for a query. | `retrieval` |
| **reasoning** | `legalai_reasoning` | The agent harness: turns a query + spans into a cited `EvidenceOutline` / `DraftAnswer`. | `reasoning` |
| **verification** | `legalai_verification` | Independently checks every claim and citation; issues `VerificationReport`. | `verification` |
| **evaluation** | `legalai_evaluation` | Golden datasets, metrics, regression suite, release gate. | `evaluation` |
| **interface** | `legalai_interface` | Composition root: wires departments into a pipeline; exposes CLI/API. | `interface` |

The **Program Office** is the main agent session (or the human lead). It owns `docs/requirements/`
triage, dispatches work, and verifies deliveries. It owns no code.

Full mission, scope and quality bars: `departments/<name>/CHARTER.md`.

## 2. Ownership (who may write where)

| Path | Owner | Others |
|---|---|---|
| `departments/<name>/**` | that department | read-only |
| `departments/contracts/**` | architecture | read-only |
| `<LEGALAI_DATA_DIR>/<name>/` (runtime data, git-ignored) | that department | no access; use the department's port |
| `docs/PRINCIPLES.md`, `docs/ORGANIZATION.md`, `docs/standards/**`, `docs/templates/**`, `docs/adr/**` | architecture | read-only; propose changes via REQ |
| `docs/requirements/REQ-<DEPT>-*.md` | issuing department writes §1–§6; receiving department writes §7 (Response) and §8 (Delivery) | read-only |
| `scripts/**`, root `pyproject.toml`, root `AGENTS.md` / `CLAUDE.md`, `.claude/**` | architecture | read-only |

A department that needs a change outside its paths files a REQ to the owner.

## 3. Data flow

```
  law: SourceDocument                      law spans (Retriever)
 corpus ─────────────────────┐            ┌──────────────────────────► reasoning
                             ▼            │   case spans                  │ EvidenceOutline
                         retrieval ───────┴─(EvidenceRetriever)──────────►│ (elements cite law,
                             ▲                                            │  links cite case files)
 casefile ───────────────────┘                                            ▼
  case: CaseDocument                                                verification ◄── re-reads exact text from
                                                                          │          SourceStore (corpus) and
                                                                          │          CaseFileStore (casefile)
                                                                          ▼ VerificationReport
                                                                      interface ──► user
 evaluation: black-box tests every stage and the whole pipeline; owns the release gate.
```

Departments never call each other directly. They implement or consume **ports** (Python
`Protocol`s) defined in `legalai_contracts.ports`. The `interface` department wires concrete
implementations together (dependency injection). This keeps core departments mutually independent.

## 4. Dependency rules (enforced by `scripts/check_boundaries.py`)

| Package | May import (besides stdlib / third-party) |
|---|---|
| `legalai_contracts` | nothing internal |
| `legalai_casefile`, `legalai_corpus`, `legalai_retrieval`, `legalai_reasoning`, `legalai_verification` | `legalai_contracts` only |
| `legalai_interface` | `legalai_contracts` + top-level public API of the five core packages |
| `legalai_evaluation` | `legalai_contracts` + top-level public API of core packages and `legalai_interface` |

"Top-level public API" means `from legalai_retrieval import X` — never `legalai_retrieval.something`.
Each package's `__init__.py` defines its public API via `__all__`.

## 5. Communication protocol

Departments communicate through three channels only:

1. **Contracts** (`legalai_contracts`): the shapes of data crossing a boundary. Versioned with semver
   (`CONTRACT_VERSION`). Breaking change → REQ to architecture + ADR.
2. **Requirement documents** (`docs/requirements/REQ-<DEPT>-<NNNN>-<slug>.md`): asks between
   departments. Template: `docs/templates/REQ.md`. Lifecycle: see `docs/requirements/README.md`.
3. **Architecture Decision Records** (`docs/adr/ADR-<NNNN>-<slug>.md`): decisions that bind more
   than one department. Only architecture creates them; anyone may request one by REQ.

No other channel counts. A decision made in chat, a code comment, or a commit message is not binding
until it is written into one of the three.

### Rules for REQs

- One REQ = one deliverable with **testable acceptance criteria**. If the reliability of legal output
  is affected, the criteria MUST include an evaluation metric and threshold.
- The issuer numbers REQs within its own prefix (`REQ-RETRIEVAL-0003`), so parallel agents never collide.
- The receiver responds in §7 (accept / reject with reason / counter-proposal) before starting work.
- The receiver records the delivery in §8 (what changed, how to verify, evidence). The **issuer**
  verifies and sets `status: verified`. The receiver never verifies its own delivery.

## 6. Multi-agent operation

- Each department has a subagent at `.claude/agents/<name>.md`. Dispatch one subagent per REQ.
- Subagents working in parallel touch disjoint directories by construction (§2), so they can run at the
  same time; use `isolation: worktree` when two subagents may touch `docs/requirements/` concurrently.
- A subagent finishes by: running `scripts/check_all.py`, filling REQ §8, and reporting back.
- Contract changes are serialized: only one architecture task at a time.
