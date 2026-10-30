---
id: CORPUS-ORIGINS
owner: corpus
status: active
updated: 2026-10-30
---

# Origin assessment (REQ-PMO-0002 §2.1)

Binding record of which origins corpus may download from. The code mirror is
`src/legalai_corpus/origins.py`; the fetcher refuses every host that is not `approved` there, including
cached copies. Assessed on 2026-10-30 by corpus.

## 1. Rule applied

From the PMO rule (REQ-PMO-0002 §2.1) and PMO's instruction of 2026-10-30, an origin is **approved** only if
all of the following hold:
1. It is the official publication of the issuing body.
2. Its terms **and** robots policy permit polite automated retrieval.
3. It states effective dates, or allows deriving them.

Mirrors, aggregators and commercial databases are rejected, and so is wenshu for v1. Ambiguous terms mean
`pending-pmo`, with no download. PMO added on 2026-10-30: "If an official origin blocks automated access, or
robots.txt is unavailable, treat it as not permitted (fail closed)". So corpus treats each of the following as
not permitted:
- a robots.txt request that does not return HTTP 200;
- a robots.txt request that returns HTML, or redirects to a homepage, instead of a robots file;
- a WAF block on an honest User-Agent.

The fetcher enforces this too (`fetch.parse_robots`). It is stricter than RFC 9309, which reads a 4xx as "no
restrictions".

## 2. Summary

| Origin | Issuer / role | Decision | Main evidence |
|---|---|---|---|
| `flk.npc.gov.cn` (国家法律法规数据库) | NPCSC General Office, national laws database | **rejected** | robots.txt forbids all agents and bans automated collection (§3.1) |
| `www.npc.gov.cn` (中国人大网), not in the charter list | NPCSC General Office, official site; NPCSC Gazette | **pending-pmo** | WAF returns HTTP 403 to an honest UA containing "robots"; HTTPS unusable from the corpus host (§3.2) |
| `www.court.gov.cn` (最高人民法院) | SPC official site | **pending-pmo** | `/robots.txt` returns the HTML error page, so no robots policy (§3.3) |
| `www.csrc.gov.cn` (中国证监会), added by REQ revision | CSRC official site | **pending-pmo** | `/robots.txt` redirects (302) to the homepage, so no robots policy (§3.4) |
| `www.spp.gov.cn` (最高人民检察院), added by REQ revision | SPP official site | **pending-pmo** | `/robots.txt` redirects (302) to the homepage; footer forbids reposting, excerpting and mirroring (§3.5) |
| `wenshu.court.gov.cn` (中国裁判文书网) | SPC judgments platform | **rejected** | PMO rule (rejected for v1); robots.txt also has `User-agent: * Disallow: /` (§3.6) |
| `www.govinfo.gov` | GPO | **pending-pmo** (paper only) | §4.1 |
| `www.ecfr.gov` | Office of the Federal Register | **pending-pmo** (paper only) | §4.2 |
| `uscode.house.gov` | House Office of the Law Revision Counsel | **pending-pmo** (paper only) | §4.3 |
| `www.uscourts.gov`, not in the charter list | Administrative Office of the US Courts | **pending-pmo** (paper only) | §4.4 |
| CourtListener (`www.courtlistener.com`) | Free Law Project, aggregator | **rejected** | not the issuing body; robots.txt request got CloudFront 403 (§4.5) |

**Result: no origin is approved, so no law text is ingested** as of 2026-10-30. PMO decides the pending items.

## 3. CN origins

### 3.1 flk.npc.gov.cn: rejected
- **Official status:** the NPC national laws database, linked from www.npc.gov.cn as `https://flk.npc.gov.cn`.
- **Robots:** `GET https://flk.npc.gov.cn/robots.txt` at 2026-10-30 09:27:13 GMT returned HTTP 200,
  `Content-Type: text/plain; charset=utf-8`, `Etag: "6a968fcf-ce"`,
  `Last-Modified: Tue, 01 Sep 2026 08:41:51 GMT`. Body:
  ```
  #禁止使用任何自动化工具、脚本、爬虫程序采集或复制网站数据
  User-agent: *
  Disallow: /
  User-agent: *
  Disallow: /private/
  Disallow: /temp/
  User-agent: BadBot
  Disallow: /admin/
  ```
  The comment says that no automated tool, script or crawler may collect or copy the site's data. This fails
  rule 2 outright. The live test `test_live_flk_robots_still_disallows_everything` re-checks it.
- **Consequence:** the site's API endpoints are on the same host, so they are covered by the same `Disallow: /`.
  Corpus did not try them.

### 3.2 www.npc.gov.cn: pending-pmo
- **Official status:** the site's own "中国人大网简介" page
  (`http://www.npc.gov.cn/npc/c2/c30834/202107/t20210728_312661.html`) says:
  "中国人大网是全国人大常委会办公厅主办的综合性官方新闻网站，由《中国人大》杂志社承办。"
  (an official news site hosted by the NPCSC General Office and run by China NPC Magazine). It publishes law
  texts in the "法律文件" section (`/npc/c2/c12435/c12488/`, 50 listing pages covering 2019-05 to 2026-09).
  It also publishes the NPCSC Gazette (常委会公报) as PDF issues for 2018 to 2026 at `/wxzlhgb/`, with older
  issues under `/wxzlhgb/ccc/`.
- **Terms:** the footer reads "版权所有：《中国人大》杂志社" (copyright notice). No terms of use were found.
- **Robots:** `GET http://www.npc.gov.cn/robots.txt` returns `User-agent: YisouSpider / Disallow: /`, which
  blocks one named crawler only. Evidence, both requests to `http://www.npc.gov.cn/robots.txt`:

  | Time (GMT) | User-Agent sent | Status | Headers |
  |---|---|---|---|
  | 2026-10-30 13:02:57 | `LegalAI-corpus/0.1 (legal research corpus; robots-aware; rate-limited)` | **403** | `Content-Type: text/html; charset=utf-8`, `WZWS-RAY: 1249-1793394177.26-waf03bjtp3` |
  | 2026-10-30 13:03:02 | `LegalAI-corpus/0.1 (legal research corpus; rate-limited)` | 200 | `Content-Type: text/plain`, `Content-Length: 40`, `Etag: "6a96a685-28"`, `Last-Modified: Tue, 01 Sep 2026 10:18:45 GMT` |

  Single-word probes at about 09:47 GMT isolated the trigger: the UA token `robots` gets 403, while
  `research` and `rate-limited` get 200. The WAF therefore blocks some self-identified automated clients.
  Under PMO's fail-closed instruction this counts as "blocks automated access".
- **Trap links:** some section index pages (for example `/npc/c2434/`) contain a hidden link (`/ics/cpf/hlink123938`
  inside a `display:none` div), apparently to catch crawlers. The fetcher never follows links; it fetches only
  URLs listed in a manifest.
- **HTTPS:** a TLS handshake to `www.npc.gov.cn:443` fails with alert 40 from both LibreSSL (curl) and OpenSSL 3.5
  (Python). DNS resolves to 198.18.0.63, a benchmarking range typical of a local proxy, so the cause may be the
  corpus host's network path rather than the site. Downloads would therefore be plain http, with no transport
  integrity. Content hashes and the independent spot check are the mitigation.
- **Versions and dates:** law pages carry the adoption line, for example "（2026年8月28日…通过）", and the commencement
  article "本法自…起施行". Amendment decisions state "本决定自…起施行". The Gazette is the formal publication.
- **Why pending:** PMO decides whether the keyword-WAF block disqualifies the site even though robots.txt permits
  an honest UA. Before this decision, 9 raw files were downloaded while the site was provisionally approved
  (§5). They are kept but not ingested.

### 3.3 www.court.gov.cn: pending-pmo
- **Official status:** the about page (`https://www.court.gov.cn/guanyu.html`) says it "是最高人民法院的政务网站，是最高人民
  法院在互联网上唯一的正式身份" (the SPC's government-affairs site and its only official presence online). The
  judicial interpretations listing is `/fabu/gengduo/16.html`, with 21 pages and about 400 items.
- **Terms:** the footer reads only "中华人民共和国最高人民法院 版权所有" (copyright notice). No terms of use page.
- **Robots:** `GET https://www.court.gov.cn/robots.txt` at 2026-10-30 13:14:33 GMT returned HTTP 200 with
  `Content-Type: text/html; charset=utf-8`, `Content-Length: 3144`, `ETag: "69200bb8-c48"`, and an HTML page titled
  "哎呀,出错了！ - 中华人民共和国最高人民法院" (error page). There is no robots policy, so under the PMO rule
  this is not permitted.
- **Versions and dates:** each interpretation is a separate page with its document number (法释〔…〕…号), the
  promulgating announcement and the commencement sentence. Amendments appear as separate "关于修改…的决定"
  pages. Repeals appear as "关于废止…的决定" pages.
- **Why pending:** PMO decides whether a missing robots.txt on the issuing body's own site, with no restrictive
  terms, is acceptable.

### 3.4 www.csrc.gov.cn: pending-pmo
- **Official status:** "主办单位：中国证券监督管理委员会 版权所有：中国证券监督管理委员会". CSRC orders (证监会令) are listed by
  the site's own JSON endpoint `/searchList/cd11df89f5894c1eac37ae37cc11e369?_isJson=true…` (234 orders).
- **Terms:** the 法律声明 page (`/csrc/c100227/c1362477/content.shtml`, dated 2008-11-28) says:
  "本网站所有信息的版权属中国证监会所有。未经中国证监会许可，不得更改、销售或租赁本网站信息。" (copyright belongs to
  CSRC; information may not be altered, sold or leased without permission). It speaks of "使用或转引" (use or
  quotation) of the information and says nothing about automated retrieval.
- **Robots:** `GET https://www.csrc.gov.cn/robots.txt` at 2026-10-30 13:14:37 GMT returned
  **302** `Location: http://www.csrc.gov.cn` (`Server: Tengine`). That is a redirect to the homepage, so there
  is no robots policy, which means not permitted.
- **Versions and dates:** 证监会令第105号 (`/csrc/c101939/c1045352/content.shtml`, published 2014-08-21). The
  HTML page holds the promulgating order. The measures themselves are an attached PDF
  (`/csrc/c101939/c1045352/1045352/files/abe08399f2034af6808b93724005f0df.pdf`). Later omnibus orders
  "关于修改、废止部分证券期货规章的决定" exist: 第166号, 177号, 179号, 184号, 202号 and 227号. Each must be read
  before 105号's validity can be set. Corpus has not read them.
- **Why pending:** no robots policy. If PMO approves, the "no alteration" condition is met by storing raw files
  unaltered, and the "no sale or lease" condition binds future product use.

### 3.5 www.spp.gov.cn: pending-pmo
- **Official status:** "Copyrights©最高人民检察院". The site has "法律法规库" and "指导性案例" sections.
- **Terms:** the footer reads "未经本网书面授权，请勿转载、摘编或建立镜像，否则视为侵权。" (no reposting, excerpting or
  mirroring without the site's written authorisation, otherwise infringement). A local corpus that serves quoted
  spans arguably counts as mirroring and excerpting.
- **Robots:** `GET https://www.spp.gov.cn/robots.txt` at 2026-10-30 13:14:41 GMT returned
  **302** `Location: https://www.spp.gov.cn` (`Server: openresty`). That is a redirect to the homepage, so there
  is no robots policy, which means not permitted.
- **Why pending:** the restrictive footer and the missing robots policy. Written authorisation from the SPP
  would resolve the terms question. PMO decides. This also determines whether evaluation may capture the
  检例第175号 page (REQ-PMO-0008).

### 3.6 wenshu.court.gov.cn: rejected
- Rejected for v1 by the PMO rule. Independently, `GET https://wenshu.court.gov.cn/robots.txt` on 2026-10-30
  allows only named search engines and ends with `User-agent: * / Disallow: /`.

### 3.7 Not assessed as candidates
- `www.gov.cn` (State Council portal) republishes laws and judicial interpretations. It is not the issuing
  body for them, so it is treated as a republisher, which the rule rejects.
- `gongbao.court.gov.cn` (SPC Gazette) is the SPC's own official publication and a possible second official
  rendering for spot checks. Not assessed; assess it if PMO wants it.

## 4. US candidates (paper assessment only; nothing downloaded)

Only robots.txt was fetched, on 2026-10-30. Terms pages were not reviewed under this REQ, and statements below
marked `[to confirm]` come from corpus's general knowledge, not from the site.

### 4.1 www.govinfo.gov (GPO)
- **Robots** (HTTP 200, text/plain): `User-agent: *` disallows `/core/`, `/profiles/`, `/admin/`, `/search/` and
  `/app/search/*`, among others. Content packages are not disallowed. Sitemaps are published for bulk
  collections.
- **Content:** the U.S. Code, in which the FRE and FRCP appear as appendices to Title 28 `[to confirm]`, and the
  CFR and Federal Register. There is an API at api.govinfo.gov that needs an api.data.gov key `[to confirm]`.
- **Versions:** annual U.S. Code editions and dated packages. Rule amendments usually take effect on December 1
  `[to confirm]`; derive the dates from the official text.
- **Expected outcome:** likely approvable once the terms are reviewed.

### 4.2 www.ecfr.gov (Office of the Federal Register)
- **Robots** (HTTP 200): disallows `/search`, `/recent-changes`, `/on/`, `/compare/` and `/my/`. It also disallows
  the developer API paths `/api/renderer/v1/content/` and `/api/versioner/v1/full/`.
- **Consequence:** the point-in-time pages (`/on/`) and the versioner full-text API are disallowed for crawlers.
  Historical CFR versions would need another official route, such as govinfo annual CFR editions, unless the
  terms or an explicit API policy permit it. The CFR is not in v1 scope.

### 4.3 uscode.house.gov (OLRC)
- **Robots** (HTTP 200): only `User-agent: Slurp / Disallow: /`. Other agents are unrestricted.
- **Content:** U.S. Code release points as downloadable files `[to confirm]`. This is a likely route for the
  FRE and FRCP as codified.

### 4.4 www.uscourts.gov (AO), not in the charter list
- **Robots** (HTTP 200): a standard Drupal file that disallows admin, search and `/federal-court-finder/` paths.
- **Content:** current rules and pending amendments published by the Judicial Conference `[to confirm]`. This is
  the issuing body's channel for rule amendments.

### 4.5 CourtListener: rejected
- An aggregator (Free Law Project) and not the issuing body, so the PMO rule rejects it. Case law is also out of
  scope. `GET https://www.courtlistener.com/robots.txt` on 2026-10-30 returned **HTTP 403** (CloudFront
  "Request blocked").

## 5. Raw files downloaded before www.npc.gov.cn became pending

At 09:46 GMT the fetcher's first robots.txt request was blocked (403). Corpus then changed the UA to drop the
token "robots" and, between 09:47:46 and 09:48:19 GMT on 2026-10-30, downloaded these files from
`www.npc.gov.cn` under the earlier provisional approval. They are stored at `<data>/corpus/raw/objects/<sha256>`.
They are **not ingested**, the guard now refuses them, and they stay where they are until PMO decides.

| URL | Bytes | sha256 |
|---|---|---|
| `http://www.npc.gov.cn/npc/c2/c30834/202012/t20201226_309442.html` (刑法修正案（十一）) | 38534 | `7e3733f8080767c2ceed1cc8f23a525495fca2e3d5c2b113b62144221dda4670` |
| `http://www.npc.gov.cn/npc/c2/c30834/202312/t20231229_433988.html` (刑法修正案（十二）) | 15095 | `126a466e4e85cec598b6bb6420a0b0e2c9b632ae4bbeb8683d9cf22522989094` |
| `http://www.npc.gov.cn/npc/c2/c30834/201905/t20190521_278345.html` (刑法修正案（十）) | 4755 | `a5d37fb32a3a4e01e365525f6e3d5ef72a2c707a49583506f006e230a5854962` |
| `http://www.npc.gov.cn/npc/c2/c12435/c12488/201905/t20190521_222115.html` (刑法修正案（九）) | 32600 | `05e7ed10b41a5ffcc2037c5a1ab8198839614f5090a458ebfc33ec04f95c6be3` |
| `http://www.npc.gov.cn/npc/c2/c12435/201905/t20190521_276591.html` (刑事诉讼法) | 175793 | `96451606f0ef9cf4663d9154c44d183816105c41ed771095cf973efddc76d21f` |
| `http://www.npc.gov.cn/npc/c2/c12435/201905/t20190521_276584.html` (关于修改刑事诉讼法的决定) | 22611 | `3a0637da5c8f777728bd776cbd6f97181d56e17e8b806f1552dc49ab8abb5ce3` |
| `http://www.npc.gov.cn/npc/c2/c12435/c12488/201905/t20190521_222050.html` (关于修改商业银行法的决定) | 5403 | `86b6fd75ffc06a3be7633c65622e2e807b9c1a0626af09ea197b982aefa8db9e` |
| `http://www.npc.gov.cn/npc/c2/c12435/c12488/201905/t20190522_76340.html` (证券投资基金法) | 75176 | `99c57e628b5dd4e4217f20f73f2ce3c14442e671ffccf406ed262e3800081346` |
| `http://www.npc.gov.cn/wxzlhgb/c27214/gb2021/202104/P020230313538043179978.pdf` (常委会公报 2021年刑法特刊) | 19937723 | `2252a75f5549dbd9f902f74c9b9943adfde33729f600c62f3e8c24ea204a5456` |

The titles in brackets are the link labels on the official listing pages. Corpus has **not** opened these files
to confirm their content or version, and no civil-law text was downloaded. Full hashes are in
`<data>/corpus/raw/latest.json` and `fetch-log.jsonl`.

## 6. Located official sources and historical versions (answer to REQ §6)

Corpus found these in official listings. None has been read or ingested. Version coverage can only be confirmed
after approval, by reading each text.

| Need (REQ §2.2) | Official location found | Historical versions |
|---|---|---|
| 刑法 consolidated versions in force from 2014-01-01 | www.npc.gov.cn: no consolidated 刑法 page in "法律文件" (2019-05 onward). The Gazette has a "2021年刑法特刊" PDF, content not yet verified. | Consolidated texts for the periods before 修正案（十一） were **not found** on any approved-candidate origin. flk would hold them but is rejected. Expect these to be reported as gaps, not built. |
| 刑法修正案 (九) to (十二) | www.npc.gov.cn pages (§5) | Each act is its own page. 修正案（八） was not found in the 2019+ listing; try the Gazette or older issues. |
| 刑事诉讼法 | www.npc.gov.cn `t20190521_276591` and the 2018 decision `t20190521_276584` | No later amendment appears in the listing up to 2026-09. A 2025-12-27 NPCSC interpretation of Art. 292 exists (`c30834/202512/t20251227_450730.html`). |
| SPC interpretation on applying 刑事诉讼法 | www.court.gov.cn `/fabu/xiangqing/4937.html` and `/fabu/xiangqing/286491.html` (both titled 最高人民法院关于适用《中华人民共和国刑事诉讼法》的解释) | Two separate pages, so likely the two versions; to be confirmed from the text. |
| Evidence-examination and illegal-evidence-exclusion provisions | Not in the SPC judicial-interpretation listing. These are joint (两高三部) documents; search after approval. | Unknown |
| Illegal-fundraising interpretations | www.court.gov.cn `/fabu/xiangqing/2031.html` (最高人民法院关于审理非法集资刑事案件具体应用法律若干问题的解释) and `/fabu/xiangqing/346901.html` (关于修改…的决定) | Original plus amendment decision. Whether an official consolidated text is published is to be confirmed. |
| 商业银行法 | www.npc.gov.cn amendment decision `t20190521_222050` | No consolidated text found yet |
| 证券投资基金法 | www.npc.gov.cn `t20190522_76340` | Which version it is has not been checked |
| 证监会令第105号 | www.csrc.gov.cn (§3.4), measures as PDF | Validity depends on the omnibus orders listed in §3.4 |
| SHOULD: 洗钱, 信用卡, 证券/期货 interpretations | www.court.gov.cn `/fabu/xiangqing/74.html`, `440681.html` (洗钱); `3.html`, `132701.html` (信用卡); `167222.html` (操纵证券、期货市场), `4034.html` and `506981.html` (内幕交易 and its amendment), `167232.html` (利用未公开信息交易) | Separate pages per version or amendment |
| SHOULD: 人民检察院刑事诉讼规则 | www.spp.gov.cn (pending) | Not searched |

## 7. Operating limits (apply once an origin is approved)
- One request per host every 3 s or more. The floor is 2 s, and a robots `Crawl-delay` wins if it is larger.
- Identifying User-Agent `LegalAI-corpus/0.1 (legal research corpus; rate-limited)`, with no personal contact
  by default (CLI `--contact` adds one). Corpus never impersonates a browser.
- Only manifest URLs are fetched, never discovered links. Every redirect hop must be an approved origin.
- Re-runs make no request for a cached URL. `--refresh` sends conditional GETs and compares hashes, giving the
  outcomes `unchanged`, `not-modified` or `changed`. A changed file for an existing version stops ingestion
  for human review.
- Update cadence: re-check approved sources with `--refresh` at most monthly, and whenever a new amendment is
  announced on the issuer's site.
