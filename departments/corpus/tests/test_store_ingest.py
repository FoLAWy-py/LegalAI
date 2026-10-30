# ruff: noqa: RUF001
# (Synthetic CN-structured fixtures must use CJK full-width punctuation such as the full-width
#  parentheses, colon and comma, which the extractor and structure parser handle.)
"""SourceStore + ingestion end to end on synthetic ZZ sources (AC2, AC4, AC5; spot-check tool for AC3)."""

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from legalai_contracts import DocType, SourceDocument, SourceStore
from legalai_corpus import (
    FileSourceStore,
    IngestError,
    IntegrityError,
    IntervalOverlap,
    Manifest,
    VersionConflict,
    ingest_manifest,
)
from legalai_corpus.spotcheck import run_spotcheck
from legalai_corpus.structure import derive_units

V1 = (
    "<p>SYNTHETIC ZZ 示例法</p><p>（2090年1月1日通过）</p>"
    "<p>第一条　SYNTHETIC 初始内容。</p><p>第二条　本法自2090年3月1日起施行。</p>"
)
AMEND = (
    "<p>SYNTHETIC ZZ 关于修改示例法的决定</p>"
    "<p>一、将第一条修改为：“第一条　SYNTHETIC 修改内容。”</p>"
    "<p>二、本决定自2095年7月1日起施行。</p>"
)
V2 = (
    "<p>SYNTHETIC ZZ 示例法</p><p>（根据2095年6月1日决定修正）</p>"
    "<p>第一条　SYNTHETIC 修改内容。</p><p>第二款　新增。</p><p>第二条　本法自2090年3月1日起施行。</p>"
)


def manifest_dict(base: str) -> dict[str, object]:
    html = {"container_attr": ["id", "content"]}
    return {
        "manifest_id": "zz-test",
        "sources": [
            {"key": "v1", "url": f"{base}/law-v1.html", "format": "html", "html": html},
            {"key": "amend", "url": f"{base}/amend.html", "format": "html", "html": html},
            {"key": "v2", "url": f"{base}/law-v2.html", "format": "html", "html": html},
        ],
        "versions": [
            {
                "doc_id": "zz-example-law",
                "version_id": "v2090-03-01",
                "title": "SYNTHETIC ZZ 示例法",
                "jurisdiction": "ZZ",
                "doc_type": "statute",
                "language": "zh-CN",
                "issuer": "SYNTHETIC ZZ legislature",
                "text_source": "v1",
                "structure_profile": "cn-law",
                "effective_from": "2090-03-01",
                "effective_from_evidence": [{"source": "v1", "quotes": ["本法自2090年3月1日起施行。"]}],
                "effective_to": "2095-07-01",
                "effective_to_evidence": [{"source": "amend", "quotes": ["本决定自2095年7月1日起施行。"]}],
                "validity_note": "superseded by the amending decision",
            },
            {
                "doc_id": "zz-example-law",
                "version_id": "v2095-07-01",
                "title": "SYNTHETIC ZZ 示例法",
                "jurisdiction": "ZZ",
                "doc_type": "statute",
                "language": "zh-CN",
                "issuer": "SYNTHETIC ZZ legislature",
                "text_source": "v2",
                "structure_profile": "cn-law",
                "effective_from": "2095-07-01",
                "effective_from_evidence": [{"source": "amend", "quotes": ["本决定自2095年7月1日起施行。"]}],
                "validity_note": "no later amendment in the synthetic origin",
            },
        ],
        "gaps": [{"subject": "SYNTHETIC older version", "reason": "no official consolidated text"}],
    }


@pytest.fixture
def served(transport, zz):
    transport.set(f"{zz.base}/law-v1.html", zz.page(V1))
    transport.set(f"{zz.base}/amend.html", zz.page(AMEND))
    transport.set(f"{zz.base}/law-v2.html", zz.page(V2))
    return transport


def _ingest(make_fetcher, tmp_path: Path, zz, data: dict[str, object] | None = None, refresh: bool = False):
    manifest = Manifest.model_validate(data or manifest_dict(zz.base))
    return ingest_manifest(manifest, make_fetcher(), FileSourceStore(tmp_path), refresh=refresh)


def test_end_to_end_two_versions_non_overlapping(make_fetcher, served, tmp_path, zz) -> None:
    report = _ingest(make_fetcher, tmp_path, zz)
    assert report["versions"] == {
        "zz-example-law/v2090-03-01": "stored",
        "zz-example-law/v2095-07-01": "stored",
    }
    store = FileSourceStore(tmp_path)
    assert isinstance(store, SourceStore)
    v1, v2 = store.versions("zz-example-law")
    assert (v1.effective_from, v1.effective_to) == (date(2090, 3, 1), date(2095, 7, 1))
    assert (v2.effective_from, v2.effective_to) == (date(2095, 7, 1), None)
    assert v1.in_force_on(date(2095, 6, 30)) and not v1.in_force_on(date(2095, 7, 1))
    assert v2.in_force_on(date(2095, 7, 1)) and not v2.in_force_on(date(2095, 6, 30))
    assert v1.source_uri == f"{zz.base}/law-v1.html"
    # AC2: contract validation and hash of stored text
    for doc in store.list_documents("ZZ"):
        SourceDocument.model_validate(doc.model_dump())
        text = store.full_text(doc.doc_id, doc.version_id)
        assert hashlib.sha256(text.encode()).hexdigest() == doc.content_sha256
        assert len(text) == doc.char_count
    assert store.list_documents("CN") == []
    prov = store.get_provenance("zz-example-law", "v2090-03-01")
    assert prov["effective_to_evidence"][0]["quotes"] == ["本决定自2095年7月1日起施行。"]  # type: ignore[index]
    assert prov["compat_codepoints"] == {"policy": "reject", "found": {}, "changes": []}
    assert report["known_gaps"]


def test_get_text_is_exact_slice_and_pinpoints_resolve(make_fetcher, served, tmp_path, zz) -> None:
    _ingest(make_fetcher, tmp_path, zz)
    store = FileSourceStore(tmp_path)
    full = store.full_text("zz-example-law", "v2095-07-01")
    for a, b in [(0, 1), (3, 17), (0, len(full)), (len(full) - 1, len(full))]:
        assert store.get_text("zz-example-law", "v2095-07-01", a, b) == full[a:b]
    for bad in [(-1, 2), (5, 5), (0, len(full) + 1), (7, 3)]:
        with pytest.raises(ValueError):
            store.get_text("zz-example-law", "v2095-07-01", *bad)
    units = {u.pinpoint: u for u in store.get_units("zz-example-law", "v2095-07-01")}
    art1 = units["第一条"]
    assert full[art1.start : art1.end] == "第一条　SYNTHETIC 修改内容。\n第二款　新增。"
    assert [u.pinpoint for u in derive_units(full, "cn-law")] == [u.pinpoint for u in units.values()]


def test_rerun_is_idempotent_and_makes_no_requests(make_fetcher, served, tmp_path, zz) -> None:
    _ingest(make_fetcher, tmp_path, zz)
    n = len(served.calls)
    report = _ingest(make_fetcher, tmp_path, zz)
    assert set(report["versions"].values()) == {"unchanged"}  # type: ignore[union-attr]
    assert len(served.calls) == n


def test_upstream_change_is_detected_and_blocks_silent_overwrite(make_fetcher, served, tmp_path, zz) -> None:
    _ingest(make_fetcher, tmp_path, zz)
    served.set(f"{zz.base}/law-v2.html", zz.page(V2.replace("新增", "被人改动")))
    with pytest.raises(IngestError) as err:
        _ingest(make_fetcher, tmp_path, zz, refresh=True)
    payload = json.loads(str(err.value))
    assert payload["upstream_changed_sources"] == ["v2"]
    assert "VersionConflict" in payload["errors"]["zz-example-law/v2095-07-01"]
    store = FileSourceStore(tmp_path)
    assert "新增" in store.full_text("zz-example-law", "v2095-07-01")  # stored version untouched


def test_evidence_quote_must_exist_verbatim(make_fetcher, served, tmp_path, zz) -> None:
    data = manifest_dict(zz.base)
    data["versions"][1]["effective_from_evidence"][0]["quotes"] = ["本决定自2095年7月2日起施行。"]  # type: ignore[index]
    with pytest.raises(IngestError, match="quote not found verbatim"):
        _ingest(make_fetcher, tmp_path, zz, data)


def test_evidence_must_state_the_date(make_fetcher, served, tmp_path, zz) -> None:
    data = manifest_dict(zz.base)
    data["versions"][1]["effective_from"] = "2095-07-02"  # type: ignore[index]
    with pytest.raises(IngestError, match="no evidence quote states the date"):
        _ingest(make_fetcher, tmp_path, zz, data)


def test_effective_to_requires_evidence() -> None:
    data = manifest_dict("https://law.zz.example")
    data["versions"][0]["effective_to_evidence"] = []  # type: ignore[index]
    with pytest.raises(ValueError):
        Manifest.model_validate(data)


def test_compat_codepoints_rejected_by_default(make_fetcher, transport, tmp_path, zz) -> None:
    transport.set(f"{zz.base}/law-v1.html", zz.page(V1.replace("初始", "初⼈")))
    transport.set(f"{zz.base}/amend.html", zz.page(AMEND))
    transport.set(f"{zz.base}/law-v2.html", zz.page(V2))
    with pytest.raises(IngestError, match="radical/compatibility code points"):
        _ingest(make_fetcher, tmp_path, zz)


def test_compat_codepoints_mapped_only_with_explicit_policy_and_recorded(
    make_fetcher, transport, tmp_path, zz
) -> None:
    transport.set(f"{zz.base}/law-v1.html", zz.page(V1.replace("初始", "初⼈")))
    transport.set(f"{zz.base}/amend.html", zz.page(AMEND))
    transport.set(f"{zz.base}/law-v2.html", zz.page(V2))
    data = manifest_dict(zz.base)
    data["sources"][0]["compat_policy"] = "map-to-unified"  # type: ignore[index]
    _ingest(make_fetcher, tmp_path, zz, data)
    store = FileSourceStore(tmp_path)
    assert "初人" in store.full_text("zz-example-law", "v2090-03-01")
    compat = store.get_provenance("zz-example-law", "v2090-03-01")["compat_codepoints"]
    assert compat["found"] == {"U+2F08": 1}  # type: ignore[index]
    assert compat["changes"][0]["from"] == "U+2F08"  # type: ignore[index]


def _doc(**kw: object) -> SourceDocument:
    text = str(kw.pop("text", "SYNTHETIC"))
    base: dict[str, object] = {
        "doc_id": "zz-d",
        "version_id": "v1",
        "title": "SYNTHETIC ZZ d",
        "jurisdiction": "ZZ",
        "doc_type": DocType.STATUTE,
        "language": "zh-CN",
        "effective_from": date(2090, 1, 1),
        "source_uri": "https://law.zz.example/d",
        "retrieved_at": "2026-01-01T00:00:00+00:00",
        "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "char_count": len(text),
    }
    base.update(kw)
    return SourceDocument.model_validate(base)


def test_store_rejects_overlap_conflict_bad_hash_and_unsafe_ids(tmp_path) -> None:
    store = FileSourceStore(tmp_path)
    assert store.put(_doc(effective_to=date(2091, 1, 1)), "SYNTHETIC", [], {}) is True
    assert store.put(_doc(effective_to=date(2091, 1, 1)), "SYNTHETIC", [], {}) is False
    with pytest.raises(IntervalOverlap):
        store.put(_doc(version_id="v2", effective_from=date(2090, 6, 1)), "SYNTHETIC", [], {})
    store.put(_doc(version_id="v2", effective_from=date(2091, 1, 1)), "SYNTHETIC", [], {})  # adjacent is fine
    with pytest.raises(VersionConflict):
        store.put(_doc(text="SYNTHETIC changed", effective_to=date(2091, 1, 1)), "SYNTHETIC changed", [], {})
    with pytest.raises(IntegrityError):
        store.put(_doc(version_id="v3", effective_from=date(2099, 1, 1)), "other text", [], {})
    with pytest.raises(ValueError):
        store.put(_doc(doc_id="../escape"), "SYNTHETIC", [], {})


def test_tampered_stored_text_is_refused(tmp_path) -> None:
    store = FileSourceStore(tmp_path)
    store.put(_doc(), "SYNTHETIC", [], {})
    path = tmp_path / "corpus" / "store" / "zz-d" / "v1" / "text.txt"
    path.write_bytes(b"SYNTHETIc")
    with pytest.raises(IntegrityError):
        FileSourceStore(tmp_path).get_text("zz-d", "v1", 0, 3)
    with pytest.raises(IntegrityError):
        FileSourceStore(tmp_path).verify_all()


def test_spotcheck_matches_and_reports_mismatch(make_fetcher, served, tmp_path, zz) -> None:
    _ingest(make_fetcher, tmp_path, zz)
    checks = tmp_path / "checks.json"
    checks.write_text(
        json.dumps(
            {
                "checks": [
                    {"doc_id": "zz-example-law", "version_id": "v2090-03-01", "pinpoint": "第一条"},
                    {"doc_id": "zz-example-law", "version_id": "v2095-07-01", "pinpoint": "第一条"},
                    {"doc_id": "zz-example-law", "version_id": "v2095-07-01", "pinpoint": "第二条"},
                    {"doc_id": "zz-example-law", "version_id": "v2095-07-01", "pinpoint": "第九条"},
                ]
            }
        )
    )
    results = run_spotcheck(tmp_path, checks)
    assert [r["match"] for r in results] == [True, True, True, False]
    assert all(r["numbering_ok"] for r in results[:3])
