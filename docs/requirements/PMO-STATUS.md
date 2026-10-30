---
id: PMO-STATUS
owner: pmo
status: active
updated: 2026-10-31
---

# Program Office status and handoff

The single place where a coordinator (Program Office, PMO) picks up the work. It unifies two PMO sessions that ran in
parallel on 2026-10-30 (the "first" session, which dispatched Wave 1, and a "second" session that committed
9ee7c03…5302cb4). Binding decisions live in REQs, ADRs and contracts (ORGANIZATION §5). This file only points to them
and records what is in flight. **REQ front matter is authoritative for status.** The index in `README.md` is
architecture-owned and may lag.

## 0. Coordinator protocol (read first)
1. **One coordinator at a time.** Before acting, run `git log --oneline -15` and `git worktree list`. If PMO commits or
   agent worktrees appear that you don't recognise, stop and ask the project owner. Two coordinators collided on
   2026-10-30, and two drafts both claimed REQ-PMO-0011.
2. Claim the role by updating §1 ("Current coordinator") in a commit. Release it the same way.
3. Number new REQs from the highest existing `REQ-PMO-NNNN` file **after** a fresh `git log`. Then commit at once.
4. Dispatch one department subagent per REQ with `isolation: worktree`. Merge with `--no-ff` and re-run
   `uv run python scripts/check_all.py` after every merge. On a `uv.lock` conflict, run `uv lock` instead of
   hand-merging.
5. **Verify independently before setting `status: verified`.** Never trust a delivery report alone (see §5 for the
   probes used so far). Only the issuer sets `verified`.
6. Every brief with network access states: an honest identifying User-Agent with **no personal data** (no owner email),
   and never change request properties to get past a refusal (REQ-PMO-0002 §7.2).
7. If an agent dies on a usage limit, resume it with SendMessage after the reset. Don't start a duplicate.

## 1. Current coordinator
**None.** Released by the first session on 2026-10-31, after unification. The next coordinator claims it here.

## 2. Project owner decisions (all dated 2026-10-30 unless noted)
| # | Decision | Recorded in |
|---|---|---|
| D6 | v1 practice area: **CN criminal cases, financial-crime focus** (replaces civil contract disputes) | ADR-0006; PROJECT.md |
| D10 | **CN first.** US law only after the CN vertical slice is confirmed end to end. D7/D8 re-opened | ADR-0006 §6.3; PROJECT.md |
| D11 | Pilot: **SPP 检例第175号 张业强等人非法集资案**, private local copy only, never redistributed (owner, 2026-10-31: "keep 175, internal copy") | REQ-PMO-0008 |
| D3 | Origin approval delegated to PMO. Approved: court.gov.cn, csrc.gov.cn, spp.gov.cn (private local use). Rejected: flk.npc.gov.cn, wenshu, CourtListener. www.npc.gov.cn: automated retrieval with the honest UA only; a refusal is final, then manual import | REQ-PMO-0002 §7; REQ-PMO-0011 |
| D13 | **Access-control rule:** never change UA, headers, IP or timing to get past a refusal. Owner answered "allow automated fetching" for npc.gov.cn on 2026-10-31. That is read as automated fetching under this rule, not around it | REQ-PMO-0002 §7.2 |
| D12 | No constructed consolidations; the 1997 text and amendment acts are stored and cited separately; missing versions are recorded gaps | REQ-PMO-0002 §7.4 |
| D14 | **Defences:** shown as `contradicts` links (ADR-0006 §4) **and** each defence MUST cite the legal provisions supporting it (owner, 2026-10-31) | REQ-PMO-0019 |
| D15 | **Look-alike characters** may be corrected, but every correction MUST be clearly marked and traceable to the original text (owner, 2026-10-31). Confirms casefile's mapping and charter amendment (REQ-PMO-0009) | REQ-PMO-0019 |
| — | Owner chooses qualified reviewers; PMO asks when one is needed. **Not needed yet** (owner asked 2026-10-31): first needed when REQ-PMO-0008 annotations are drafted, which requires CN law ingested (0002/0011) | (owner instruction) |
| — | Owner-supplied Yu Huan pilot (`data/evaluation/yu-huan-pilot/`) is **not** golden data: doc 01 is not verbatim to the official SPC page; docs 05–07 are mirrors | REQ-PMO-0005 §1 |

## 3. REQ board
| REQ | Dept | Status | Next action |
|---|---|---|---|
| 0001 casefile intake | casefile | verified | — |
| 0002 CN criminal law | corpus | in-progress | Resume with §7 decisions plus 0011 and 0014. No law ingested yet |
| 0003 retrieval | retrieval | verified | Follow-up 0018 |
| 0004 verification | verification | verified | — |
| 0005 eval set/runner/spec | evaluation | verified | — |
| 0006 interface pipeline/CLI | interface | open | In flight in worktree `ae038e…` (second session) |
| 0007 criminal re-scope | architecture | verified | — |
| 0008 SPP 175 pilot | evaluation | draft | Open it after 0002/0011 and 0017. Needs a **qualified reviewer** (ask owner) |
| 0009 CJK look-alikes | casefile | verified | Owner confirmed (D15). Marking downstream via 0019 |
| 0010 contract gaps (0.4.0) | architecture | verified | — |
| 0011 manual import | corpus | open | In flight with corpus (`a4bd54…`) |
| 0012 adopt 0.4.0 verification | verification | open | **Delivered on branch `worktree-agent-ae0fc3fc99456b9ef`, not merged.** Verify and merge |
| 0013 adopt 0.4.0 casefile | casefile | verified | — |
| 0014 adopt 0.4.0 corpus | corpus | open | With corpus |
| 0015 adopt 0.4.0 reasoning | reasoning | open | In flight (`ad4d8b…`) |
| 0016 adopt 0.4.0 interface | interface | open | In flight (`ae038e…`) |
| 0017 adopt 0.4.0 evaluation | evaluation | open | Not dispatched |
| 0018 case-file recall | retrieval | open | Not dispatched |
| 0019 defence law basis + marked corrections | architecture | open | Not dispatched. **Contract change: run it alone** (ORGANIZATION §6). Then issue adoption REQs from its §8 |
| ARCH-0001 framework spike | reasoning | open | In flight (`ad4d8b…`). Afterwards, evaluation runs both builders live on `ZZ-SYNTH-CRIM-OUTLINE`, then ADR-0002 is decided |

## 4. Agent worktrees (as of 2026-10-31)
| Worktree | Session | State | Action |
|---|---|---|---|
| `agent-a4bd54a9e4930161d` | second | corpus, uncommitted work (7 files) | Resume or finish via its agent |
| `agent-ad4d8b9eb43ea8508` | second | reasoning spike, uncommitted (19) | Resume via its agent |
| `agent-ae038e1b2ab19b1a4` | second | interface, uncommitted (22) | Resume via its agent |
| `agent-ae0fc3fc99456b9ef` | second | verification 0012 delivered, clean | Verify, then merge |
| `agent-a6d0a098cf41168cb` | second | merged, but 16 uncommitted files | Inspect before removal |
| `agent-a249823a335a6232b` | first | reasoning spike, barely started (2 files) | **Redundant** (superseded by `ad4d8b…`); safe to remove |
| `agent-a972b1d5c66d9c94d` | first | architect 0010, uncommitted (9) | **Redundant** (0010 delivered via `a3b00b…`); safe to remove |
| other `agent-*` | both | merged and clean | Safe to remove (`git worktree remove`) |

## 5. How deliveries were verified (reuse these probes)
- **0004:** mutation test (disable the verbatim-quote check, so 7 adversarial tests must fail); live Phase B against
  `deepseek-ai/DeepSeek-V4.1-Flash-1017` on synthetic ZZ only.
- **0001 / 0009:** PDFs and DOCX made by **external** generators (`cupsfilter`, `textutil`) from synthetic Chinese text.
  This found the Kangxi-radical substitution (600/10,044 characters). After 0009: 120/120 lines exact, and the mapping
  is reversible to raw pypdf output.
- **0005:** oracle builder plus `IndependentVerifier` with a grounded approve-all model: 10/10 pass, 0/80 adversarial
  false pass; grep for real-law strings in synthetic sources.
- **0003:** recall@k through the evaluation runner with the real embedder (see REQ-PMO-0018 §1).

## 6. Open items not yet in a REQ
1. **ADR-0006 duties:**
   - verification checks rules 3.2 (`burden_on` only when cited law states it) and 4.3 (no legal rule in a link
     `purpose`);
   - reasoning abstains on incidental-civil requests (rule 2.2);
   - interface shows contradicting links next to supporting ones (rule 4.2).
   One REQ per department.
2. **Architecture:**
   - jurisdiction applicability (`US-XX` ⊇ `US`?), deferred with US;
   - move the RUF001 CJK punctuation allow-list to the root ruff config (three departments carry their own);
   - the root `.gitignore` rule `data/` also ignores package directories named `data` (trap hit by casefile and retrieval);
   - whether an open `effective_to` can be marked "not confirmed" (corpus).
3. **Corpus to confirm:** `SourceStore.list_documents(jurisdiction)` returns all versions, not only current (retrieval
   assumes so).
4. ~~Owner to confirm defences / casefile charter amendment~~: decided 2026-10-31 (D14, D15), now in REQ-PMO-0019.
5. **Owner input pending (not yet needed):** qualified CN reviewer (PRC criminal lawyer, or former prosecutor or judge, with
   illegal-fundraising experience) before 0008 annotations can gate a release.

## 7. Incidents (for the record)
- 2026-10-30: corpus exploration requests carried the **owner's email in the User-Agent** to official CN sites. It was
  stopped, the owner was informed, and REQ-PMO-0011/§0.6 now forbid it.
- 2026-10-30: corpus changed its UA once to pass npc.gov.cn's firewall. The 9 files obtained that way are to be
  deleted (REQ-PMO-0002 §7.3).
- 2026-10-30/31: two PMO sessions ran at once (see §0.1).

## 8. Remote
`origin` = https://github.com/FoLAWy-py/LegalAI.git. Only the initial commit has been pushed. Everything since then
is local on `main`. Push only when the owner asks.
