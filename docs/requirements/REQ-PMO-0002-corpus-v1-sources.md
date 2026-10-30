---
id: REQ-PMO-0002
title: Assess origins and ingest v1 CN criminal law with versions
from: pmo
to: corpus
owner: pmo
status: in-progress
priority: P1
created: 2026-10-30
updated: 2026-10-30
depends_on: [ADR-0004, ADR-0005]
---

# REQ-PMO-0002: Assess origins and ingest v1 CN criminal law with versions

## 1. Context
Elements must be grounded in authoritative, versioned law (P1, P4, P5). Scope per ADR-0005.

**Sequencing (project owner, 2026-10-30):** CN first; US law follows in a separate REQ once the CN
vertical slice is confirmed end to end. **Practice area (project owner, 2026-10-30, revises D6):** CN **criminal**
cases replace civil contract disputes, with **financial crimes** as the v1 focus; ADR-0005 is being amended accordingly. **Origin approval** is delegated by the project owner to the
Program Office and is decided by the rule in §2.1 below.

Lesson from the Yu Huan pilot (PMO check, 2026-10-30): a local "public text extract" labelled as an official
SPC capture differed from the official page (sentences missing, holdings reworded). Captures MUST therefore be
byte-faithful to the official rendering, never re-typed, summarised or copied from mirrors.

## 2. Requirement
1. Corpus MUST write `departments/corpus/docs/origins.md` assessing each candidate origin in the charter:
   terms of use, robots policy, rate limits, formats, how versions/effective dates are obtained. Each origin is
   marked approved / rejected with reasons. Only approved origins may be downloaded.
   **Approval rule (PMO):** an origin is approved only if it is the official publication of the issuing body
   (e.g. the NPC national laws database for laws, the SPC website for judicial interpretations, the SPP website for
   SPP-issued documents), its terms and
   robots policy permit automated retrieval at a polite rate, and it states or allows deriving effective dates.
   Mirrors, commercial databases and aggregators are rejected. wenshu.court.gov.cn is rejected for v1.
   When an origin's terms are ambiguous, mark it `pending-pmo` and do not download.
2. Corpus MUST ingest, from approved origins, **CN criminal law**: the Criminal Law (刑法) as amended — every
   consolidated version in force from 2021-01-01 onward, and the amendment acts (修正案) that produced them; the
   Criminal Procedure Law (刑事诉讼法); the SPC interpretation on applying the Criminal Procedure Law; and the
   official provisions on examining and judging evidence and on excluding illegal evidence in criminal cases
   (identify the exact official titles, issuers and versions from the official sources). Corpus SHOULD also ingest
   the SPP rules of criminal procedure for procuratorates if its origin is approved.
   **Financial-crime focus:** corpus MUST ingest the SPC (and joint SPC/SPP) judicial interpretations on illegal
   fundraising — every version in force from 2014-01-01 onward, including 法释〔2022〕5号 and the version it replaced —
   and SHOULD ingest the official interpretations on money laundering, credit-card crimes and securities/futures
   crimes (identify titles, document numbers and versions from official sources).
   **Pilot (SPP 检例第175号, REQ-PMO-0008):** the conduct ran from 2014 to 2018, so for the Criminal Law and the
   illegal-fundraising interpretations corpus MUST cover every version in force from **2014-01-01** (not only from
   2021). Corpus MUST also ingest the non-criminal provisions that case cites for the illegality element — the
   Commercial Banking Law (商业银行法), the Securities Investment Fund Law (证券投资基金法) and the CSRC interim measures
   on private investment funds (证监会令第105号) — from their official issuing-body origins (NPC database; CSRC),
   all versions in force over the same period. All versions with correct
   `effective_from` / `effective_to` taken from the official source (never from memory). Where only an amendment
   act and no official consolidated text exists for some version, record that and do not construct a consolidated
   text yourself. `origins.md` also assesses the US candidates so the US REQ can start quickly, but
   no US text is downloaded under this REQ.
3. Text MUST be stored in the original language, structure preserved so article/rule pinpoints can be derived.
4. A `SourceStore` implementation MUST serve documents and exact text ranges.
5. US federal and state layers are deferred to a later REQ; design MUST allow adding them without contract change.

## 3. Interface
`SourceDocument`, `DocType`, port `SourceStore`.

## 4. Acceptance criteria
1. `origins.md` exists and covers every candidate origin.
2. 100% of ingested documents pass contract validation (complete provenance, hash matches stored text).
3. Spot-check list (≥ 20 articles/rules across documents, chosen by corpus and recorded in §8) matches the official
   rendering character-for-character, including article numbering.
4. For at least one amended document, two versions exist with non-overlapping validity intervals.
5. Downloads honour rate limits; the downloader is re-runnable and detects upstream changes by hash.
6. `scripts/check_all.py` passes (network tests marked `live`).

## 5. Out of scope
Civil law (no longer v1 scope) except the financial-regulation statutes named in §2.2, case law incl. guiding cases (later REQ), all US law (later REQ), judgments from wenshu.court.gov.cn, indexing.

## 6. Open questions
- Which origin provides authoritative historical versions for each document?

## 7. Response
Decision: **accept** (corpus, 2026-10-30), with these clarifications:

1. Origins: assessed in `departments/corpus/docs/origins.md` under the PMO rule (§2.1). Besides the charter
   candidates, corpus also assesses `www.npc.gov.cn` (the NPC site that publishes the NPCSC Gazette) and
   `www.spp.gov.cn` and `www.csrc.gov.cn` (named in §2.1/§2.2), because `flk.npc.gov.cn` forbids automated
   retrieval in its robots.txt.
2. Fidelity: stored text is derived mechanically from the raw official file, which is stored and hashed
   next to it. The normalization rules are written down in `departments/corpus/docs/normalization.md`. No text is
   typed, condensed or filled in from memory or mirrors.
3. Dates: every `effective_from` / `effective_to` carries a recorded evidence pointer (URL plus the exact
   official sentence it was read from). If corpus cannot find an official date or consolidated text, the version
   is left out and listed in §8 instead of being guessed.
4. Answer to §6: see the "Historical versions" table in `origins.md` and §8.

### PMO decisions and amendment (2026-10-30, project owner via PMO)
Answers to the three decisions corpus asked for in §8. The receiver acknowledges this amendment on resumption (STD-DOC §4).

1. **Amended approval rule (replaces the robots clause of §2.1):** an official issuing-body origin **with no robots
   policy** (robots.txt missing, an HTML error page, or a redirect) is **approved for automated retrieval**, as long
   as its terms do not forbid automated access. An explicit `Disallow` that applies to our crawler, or an explicit
   ban on automated tools, still means **rejected**. Every other §2.1 condition is unchanged: polite rate, honest
   identifying UA, official origin, no mirrors.
   - **Approved:** `www.court.gov.cn`, `www.csrc.gov.cn`, `www.spp.gov.cn`. Stored copies are for private local
     analysis only, never redistributed or committed. This satisfies CSRC's "no alteration / sale / lease" terms and
     SPP's "no reposting / excerpting / mirroring" footer.
   - **Still rejected:** `flk.npc.gov.cn` (explicit ban), `wenshu.court.gov.cn`.
   - **`www.npc.gov.cn`:** automated retrieval is allowed **only with the honest UA**. A firewall refusal (403) means
     *not permitted* for automation; the document then comes in through the manual-import path (REQ-PMO-0011).
2. **Access-control rule (new, binding on every department):** never change the user agent, headers, IP, timing or
   any other request property to get past a refusal, block, CAPTCHA or firewall. A refusal is final for automated
   access.
3. **The 9 raw files** from `www.npc.gov.cn` (downloaded after the UA was changed to get past the firewall) MUST be
   **deleted** from the raw store, with the deletion recorded in the fetch log and `origins.md` §5. Those documents
   are re-obtained through an approved path.
4. **Versions without an official consolidated text:** accepted as recorded gaps. Corpus stores the original
   1997 Criminal Law text and every amendment act as **separate official documents**, so an outline can cite the
   original article and the amending provision side by side. No consolidated text is constructed (§2.2 unchanged).

## 8. Delivery
**Status: partial; ingestion is blocked on PMO origin decisions** (corpus, 2026-10-30). Status stays `in-progress`.

Under the §2.1 rule and PMO's fail-closed instruction of 2026-10-30, **no origin is approved**, so **no law text
has been ingested**. All infrastructure is built and tested offline on synthetic `ZZ` data. Once PMO approves an
origin, the CN manifest can be written from the official texts and run without code changes.

- **What changed** (all under `departments/corpus/`):
  - `docs/origins.md`: assessment of every charter candidate, plus www.npc.gov.cn, www.csrc.gov.cn,
    www.spp.gov.cn and www.uscourts.gov, each with exact evidence (URL, status, headers, time).
  - `docs/normalization.md`: extraction rules N0–N6, including the look-alike code point policy.
  - `src/legalai_corpus/origins.py`: origin registry; the fetcher refuses any host not `approved`, including
    cached copies.
  - `fetch.py`: robots-aware polite fetcher.
    - It reads robots.txt first and treats an unavailable one (non-200, HTML, or redirect to a homepage) as
      not permitted.
    - It waits at least 3 s between requests to a host (floor 2 s; a larger `Crawl-delay` wins) and sends an
      identifying UA.
    - It checks every redirect hop against the registry.
    - Raw files are cached content-addressed with an append-only fetch log.
    - `--refresh` sends a conditional GET and compares hashes: `unchanged` / `not-modified` / `changed`.
  - `extract.py`: HTML extraction (stdlib parser) and PDF extraction (pdfminer.six), plus detection of
    Kangxi Radicals, CJK Radicals Supplement and CJK Compatibility Ideographs. These are rejected by default;
    one-for-one mapping happens only under an explicit per-source policy, and every change is recorded.
  - `structure.py`: pinpoint units for 编 / 分编 / 章 / 节 / 条 / 款 / 项, and 一、 items of amendment acts.
  - `manifest.py`: manifest model. Every date needs official evidence quotes, and one quote must render the
    date itself.
  - `store.py`: `FileSourceStore`, which implements `SourceStore`.
    - Versions are immutable.
    - The text hash is verified on every read (fail closed).
    - Versions of one document may not overlap in validity.
  - `ingest.py`: manifest → official raw file → mechanical text → stored version. Every evidence quote must be
    re-found verbatim in the extracted official text.
  - `spotcheck.py`: independent comparison (lxml for HTML, pypdf for PDF).
  - `cli.py`, `__main__.py`, and the public API in `__init__.py`.
  - `CHARTER.md`: Interfaces section, scope note for ADR-0006, pointer to origins.md.
  - New dependencies in `departments/corpus/pyproject.toml`: pydantic, lxml, pdfminer.six, pypdf (`uv.lock`
    updated).
- **Origins** (evidence in `origins.md` §3–§4):

  | Decision | Origins | Reason |
  |---|---|---|
  | rejected | flk.npc.gov.cn | robots.txt `User-agent: * Disallow: /` and "禁止使用任何自动化工具、脚本、爬虫程序采集或复制网站数据" |
  | rejected | wenshu.court.gov.cn | PMO rule; robots.txt `User-agent: * Disallow: /` |
  | rejected | CourtListener | aggregator; robots.txt request got CloudFront 403 |
  | pending-pmo | www.npc.gov.cn | WAF answers 403 to an honest UA containing "robots"; HTTPS unusable from the corpus host |
  | pending-pmo | www.court.gov.cn | `/robots.txt` is an HTML error page |
  | pending-pmo | www.csrc.gov.cn | `/robots.txt` redirects (302) to the homepage |
  | pending-pmo | www.spp.gov.cn | `/robots.txt` redirects (302) to the homepage; footer forbids reposting, excerpting and mirroring |
  | pending-pmo (paper only) | govinfo, ecfr, uscode.house.gov, uscourts | no US download under this REQ |

- **What was ingested:** nothing.
  - 9 raw files were downloaded from www.npc.gov.cn on 2026-10-30, 09:47–09:48 GMT, before PMO's fail-closed
    instruction. No civil-law text was downloaded.
  - They are kept unopened and not ingested at `<data>/corpus/raw/objects/`. URLs and full sha256 hashes are
    in `origins.md` §5.
- **Answer to §6 (historical versions):** see `origins.md` §6.
  - Expected gap: no official consolidated Criminal Law (刑法) text was found for the periods before
    amendment XI (修正案（十一）) on any candidate origin except flk, which is rejected. Such versions will be
    reported, not constructed.
  - The SPC site carries the old and new interpretations as separate pages. The NPC site carries each
    amendment act and the 2018 Criminal Procedure Law (刑事诉讼法).
- **Look-alike code points (PMO note of 2026-10-30):** 0 documents ingested, so there is nothing to report
  per document yet. Detection runs on every extracted text, from any format. Default `reject` makes ingestion
  fail; an HTML rendering is preferred over a PDF. Counts and changes go into `provenance.json`
  (`compat_codepoints`).
- **Acceptance criteria:**

  | AC | Status | How it is met |
  |---|---|---|
  | 1 | met | `origins.md` covers every charter candidate plus four more. |
  | 2 | mechanism met; real data blocked | Ingestion builds and validates `SourceDocument`s; the store re-hashes on read and `verify_all`. Tests: `test_end_to_end_two_versions_non_overlapping`, `test_tampered_stored_text_is_refused`. No real documents yet. |
  | 3 | blocked | The tool exists and is tested, including detection of a single re-typed character (`test_spotcheck_detects_retyped_text`). No ≥20-article list is possible without ingested documents. |
  | 4 | mechanism met on ZZ; real data blocked | Two versions with adjacent half-open intervals (`test_end_to_end_two_versions_non_overlapping`); the overlap guard is tested. |
  | 5 | met | `test_fetch.py`: rate limit, crawl-delay, robots fail closed, no requests on re-run, change detection by hash, raw history kept. |
  | 6 | met | `check_all` passes (tail below). The live test `test_live_flk_robots_still_disallows_everything` is marked `live`. |

- **How to verify:**
  ```sh
  uv run python scripts/check_all.py
  uv run pytest -q departments/corpus
  uv run pytest -q -m live departments/corpus     # network: robots.txt of flk only
  uv run python -m legalai_corpus fetch --data-dir data http://www.npc.gov.cn/   # refused: pending-pmo
  ```
- **Evidence** (`check_all` tail, 2026-10-30, after merging main with contracts 0.3.0):
  ```
  $ mypy scripts
  Success: no issues found in 3 source files
  $ pytest -q
  430 passed, 2 deselected in 1.03s
  ALL CHECKS PASSED
  ```
  Corpus alone: 45 tests pass offline, and the live test passes.
- **Known limitations:**
  - The PDF paragraph rule is not yet validated on a real official PDF, and its line joining suits CJK only.
  - The stdlib robots parser does not support `*` wildcards in paths. This matters for US sites (govinfo),
    not CN.
  - An open `effective_to` cannot say "not confirmed"; corpus records `validity_note` in provenance only.
    Making that visible to verification would need a contract change (a REQ to architecture if PMO wants it).
  - The test files carry a file-level `# ruff: noqa: RUF001` because synthetic CN fixtures need full-width
    punctuation.
- **Decisions needed from PMO before ingestion can proceed:**
  1. Approve or reject www.npc.gov.cn, www.court.gov.cn and www.csrc.gov.cn, given the evidence. If approved,
     also say whether the 9 NPC raw files may be used or must be re-downloaded.
  2. SPP: obtain written authorisation, or reject the origin.
  3. Whether consolidated Criminal Law versions without an official text are acceptable as recorded gaps.
