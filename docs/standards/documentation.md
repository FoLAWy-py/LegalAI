---
id: STD-DOC
owner: architecture
status: active
updated: 2026-10-30
---

# Documentation Standard

## 1. General rules

1. **Language:** English for all repository documents, identifiers and commit messages.
   Legal source text keeps its original language; translations are marked as such.
2. **Normative keywords:** MUST, MUST NOT, SHOULD, SHOULD NOT, MAY carry RFC 2119 meaning. Use them
   only in rules; write them in capitals.
3. **One topic per document.** Link instead of duplicating. If two documents disagree, the one higher
   in this order wins: `PRINCIPLES.md` > accepted ADR > `ORGANIZATION.md` > standards > charters > REQs.
4. **Dates** are ISO 8601 (`2026-10-30`). Never write relative dates ("next week").
5. **Filenames** are kebab-case, ASCII. IDs are uppercase with hyphens.
6. **Short and concrete.** Prefer tables and numbered rules to prose. Every rule must be checkable.
7. **No legal content without a source.** Any statement about the law in a document cites its source
   per `legal-content.md`, or is marked `[UNVERIFIED]`.

## 2. Document types

| Type | Location | ID pattern | Template | Who creates |
|---|---|---|---|---|
| Principle / org / standard | `docs/`, `docs/standards/` | `PRINCIPLES`, `STD-<NAME>` | — | architecture |
| ADR | `docs/adr/` | `ADR-0001` | `templates/ADR.md` | architecture |
| Requirement | `docs/requirements/` | `REQ-<DEPT>-0001` | `templates/REQ.md` | any department |
| Charter | `departments/<name>/CHARTER.md` | `CHARTER-<DEPT>` | `templates/CHARTER.md` | that department (scope changes need architecture approval) |
| Department notes | `departments/<name>/docs/` | free | — | that department |

## 3. Front matter

Every document under `docs/` and every charter starts with YAML front matter.
Required keys for all: `id`, `owner`, `status`, `updated`.

Additional keys:

- **REQ:** `title`, `from`, `to`, `priority` (`P0`–`P3`), `created`, `depends_on` (list of IDs, may be empty).
- **ADR:** `title`, `deciders`, `supersedes` / `superseded_by` (optional).

Allowed `status` values:

| Type | Values |
|---|---|
| REQ | `draft`, `open`, `accepted`, `rejected`, `in-progress`, `delivered`, `verified`, `closed` |
| ADR | `proposed`, `accepted`, `rejected`, `superseded` |
| Others | `draft`, `active`, `deprecated` |

`scripts/check_docs.py` validates front matter and filenames.

## 4. Changing documents

- Update `updated:` on every substantive edit.
- Accepted ADRs are immutable except for status; supersede them with a new ADR.
- REQ acceptance criteria are frozen once `accepted`. Changing them means a new REQ or an explicit
  amendment note in §7 agreed by both departments.

## 5. Code-level documentation

- Every public function/class in a package's `__all__` has a docstring stating what it guarantees,
  not how it works.
- Comments explain *why*, never restate *what*.
- Prompts are documents: each prompt file has a header with `prompt_id`, `version`, `owner`, and a
  changelog line per version.

## 6. Agent instruction files

- `AGENTS.md` is the **only** place for agent rules (root and one per department). It is tool-neutral:
  plain Markdown, no tool-specific syntax such as `@imports`.
- `CLAUDE.md` exists only so Claude Code loads the rules. It contains nothing but `@` import lines
  (`@AGENTS.md`, and `@CHARTER.md` in departments). `scripts/check_docs.py` enforces this.
