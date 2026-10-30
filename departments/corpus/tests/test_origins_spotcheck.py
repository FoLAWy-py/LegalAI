# ruff: noqa: RUF001
# (Synthetic CN-structured fixtures must use CJK full-width punctuation such as the full-width
#  parentheses, colon and comma, which the extractor and structure parser handle.)
"""Origin registry invariants; spot check detects re-typed text; live robots check (marked live)."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from legalai_contracts import DocType, SourceDocument
from legalai_corpus import ORIGINS, FileSourceStore, OriginNotApproved, OriginStatus, RawStore
from legalai_corpus.extract import HtmlRule, extract_html
from legalai_corpus.fetch import HttpResponse, parse_robots
from legalai_corpus.origins import require_approved
from legalai_corpus.spotcheck import run_spotcheck
from legalai_corpus.store import text_sha256
from legalai_corpus.structure import derive_units


def test_registry_is_consistent() -> None:
    hosts = [h for o in ORIGINS for h in o.hosts]
    assert len(hosts) == len(set(hosts))
    assert all(o.reason for o in ORIGINS)
    by_key = {o.key: o for o in ORIGINS}
    assert by_key["cn-wenshu"].status is OriginStatus.REJECTED  # PMO rule: rejected for v1
    assert by_key["cn-npc-flk"].status is OriginStatus.REJECTED  # robots.txt Disallow: /


def test_no_origin_approved_without_pmo_decision() -> None:
    """State of record 2026-10-30 (origins.md): every remaining origin awaits PMO; nothing is downloadable."""
    assert [o.key for o in ORIGINS if o.status is OriginStatus.APPROVED] == []
    for url in ("http://www.npc.gov.cn/x", "https://www.court.gov.cn/x", "https://www.csrc.gov.cn/x"):
        with pytest.raises(OriginNotApproved):
            require_approved(url)


def test_robots_with_wildcard_disallow_blocks() -> None:
    body = "#禁止使用任何自动化工具\nUser-agent: *\nDisallow: /\n".encode()
    parser, _, reason = parse_robots(
        HttpResponse(200, "https://x/robots.txt", {"content-type": "text/plain"}, body), "UA"
    )
    assert reason is None and parser is not None
    assert not parser.can_fetch("LegalAI-corpus/0.1", "https://x/anything")


def test_spotcheck_detects_retyped_text(tmp_path: Path, zz) -> None:
    """Regression for the Yu Huan lesson: stored text that differs from the raw official file must fail."""
    raw = zz.page("<p>SYNTHETIC ZZ 法</p><p>第一条　SYNTHETIC 原始文字，不得改写。</p><p>第二条　其他。</p>")
    raw_store = RawStore(tmp_path / "corpus")
    digest = raw_store.put_object(raw)
    official = extract_html(raw, HtmlRule(("id", "content")))
    retyped = official.replace("不得改写", "不能改写")  # one character re-typed
    store = FileSourceStore(tmp_path)
    for version_id, text in (("official", official), ("retyped", retyped)):
        doc = SourceDocument(
            doc_id="zz-retype",
            version_id=version_id,
            title="SYNTHETIC ZZ 法",
            jurisdiction="ZZ",
            doc_type=DocType.STATUTE,
            language="zh-CN",
            effective_from=datetime(2090 + (version_id == "retyped") * 10, 1, 1).date(),
            effective_to=datetime(2100, 1, 1).date() if version_id == "official" else None,
            source_uri=f"{zz.base}/retype",
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
            content_sha256=text_sha256(text),
            char_count=len(text),
        )
        provenance = {
            "raw": {"sha256": digest, "final_url": f"{zz.base}/retype"},
            "extraction_rule": {
                "format": "html",
                "html": {"container_attr": ["id", "content"], "encoding": "utf-8"},
            },
        }
        store.put(doc, text, derive_units(text, "cn-law"), provenance)
    checks = tmp_path / "c.json"
    checks.write_text(
        json.dumps(
            {
                "checks": [
                    {"doc_id": "zz-retype", "version_id": v, "pinpoint": "第一条"}
                    for v in ("official", "retyped")
                ]
            }
        )
    )
    official_row, retyped_row = run_spotcheck(tmp_path, checks)
    assert official_row["match"] is True
    assert retyped_row["match"] is False and retyped_row["content_ok"] is False


@pytest.mark.live
def test_live_flk_robots_still_disallows_everything() -> None:
    """Network: confirms the evidence behind rejecting flk.npc.gov.cn (fetches robots.txt only)."""
    import urllib.request

    req = urllib.request.Request(
        "https://flk.npc.gov.cn/robots.txt", headers={"User-Agent": "LegalAI-corpus/0.1"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read()
        status = resp.status
    parser, _, reason = parse_robots(
        HttpResponse(status, resp.url, {"content-type": "text/plain"}, body), "UA"
    )
    assert reason is None and parser is not None
    assert not parser.can_fetch("LegalAI-corpus/0.1", "https://flk.npc.gov.cn/")
