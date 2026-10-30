"""REQ-PMO-0013: contracts 0.4.0 adoption (ADR-0007 §3 not-found error, §4 original_sha256).

All documents are synthetic (jurisdiction ZZ); no real case data.
"""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import legalai_contracts
from legalai_casefile import (
    CasefileError,
    DocumentNotFoundError,
    LocalCaseFileStore,
    StoreIntegrityError,
)
from legalai_casefile._pdf_corpus import astral_pages, mixed_pages, zh_pages
from legalai_casefile._synthetic_docs import build_docx, para
from legalai_casefile._synthetic_pdf import build_pdf

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
CASE = "case-zz-0013"
EXTERNAL = Path(__file__).parent / "fixtures" / "external"
TXT = b"SYNTHETIC ZZ text.\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _corpus() -> dict[str, bytes]:
    """One synthetic file per supported format, plus the external CJK-radical PDF fixture."""
    return {
        "SYNTHETIC-合同.pdf": build_pdf(zh_pages(), "SYNTHETIC contract"),
        "SYNTHETIC-mixed.pdf": build_pdf((*mixed_pages(), *astral_pages()), "SYNTHETIC receipt"),
        "SYNTHETIC-radicals.pdf": (EXTERNAL / "zz-radicals-cupsfilter.pdf").read_bytes(),
        "SYNTHETIC-补充协议.docx": build_docx(para("SYNTHETIC 补充协议（ZZ）") + para("Party A / 甲方")),
        "SYNTHETIC-催款函.txt": "SYNTHETIC 催款函\r\n示例乙：尚欠货款。\r\n".encode(),
        "SYNTHETIC-gbk.txt": "SYNTHETIC 示例 ZZ\n".encode("gb18030"),
        "SYNTHETIC-memo.md": "# SYNTHETIC Memo 备忘录\n\n甲方同意。\n".encode(),
        "SYNTHETIC-对账.eml": (
            b"From: a@example.zz\r\nTo: b@example.zz\r\nSubject: SYNTHETIC statement\r\n"
            b"Date: Fri, 30 Oct 2026 09:00:00 +0800\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
            b"SYNTHETIC body ZZ.\r\n"
        ),
    }


def _encoding(name: str) -> str | None:
    return "gb18030" if name == "SYNTHETIC-gbk.txt" else None


def _edit_meta(tmp_path: Path, change: Callable[[dict[str, Any]], None]) -> Path:
    """Apply `change` to the single stored meta.json (simulating an older or tampered record)."""
    meta_path = next(tmp_path.glob("casefile/cases/*/*/*/meta.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    change(meta)
    meta_path.chmod(0o600)
    meta_path.write_bytes(json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))
    return meta_path


# ---- AC1: not-found is the contract error -------------------------------------------------------------


def test_casefile_not_found_subclasses_contract_error() -> None:
    assert issubclass(DocumentNotFoundError, legalai_contracts.DocumentNotFoundError)
    assert issubclass(DocumentNotFoundError, CasefileError)
    assert issubclass(DocumentNotFoundError, LookupError)


def test_missing_document_is_caught_as_contract_error(tmp_path: Path) -> None:
    store = LocalCaseFileStore(tmp_path)
    with pytest.raises(legalai_contracts.DocumentNotFoundError) as unknown_doc:
        store.get_document("cf-missing", "v0001-000000000000")
    assert unknown_doc.value.doc_id == "cf-missing"
    assert unknown_doc.value.version_id == "v0001-000000000000"
    with pytest.raises(legalai_contracts.DocumentNotFoundError):
        store.get_text("cf-missing", "v0001-000000000000", 0, 1)

    doc = store.ingest(CASE, "SYNTHETIC.txt", TXT, received_at=T0).document
    calls: list[Callable[[], object]] = [
        lambda: store.get_document(doc.doc_id, "v0009-000000000000"),
        lambda: store.get_text(doc.doc_id, "v0009-000000000000", 0, 1),
    ]
    for call in calls:
        with pytest.raises(legalai_contracts.DocumentNotFoundError) as unknown_version:
            call()
        assert unknown_version.value.doc_id == doc.doc_id
        assert unknown_version.value.version_id == "v0009-000000000000"
        assert "SYNTHETIC" not in str(unknown_version.value)  # ids only, never text (P9)


def test_integrity_failure_is_not_a_not_found(tmp_path: Path) -> None:
    """Fail closed (ADR-0007 §3.4): a tampered store must not look like an absent document."""
    doc = LocalCaseFileStore(tmp_path).ingest(CASE, "SYNTHETIC.txt", TXT, received_at=T0).document
    text = next(tmp_path.glob("casefile/cases/*/*/*/text.txt"))
    text.chmod(0o600)
    text.write_bytes(TXT.upper())
    with pytest.raises(StoreIntegrityError) as exc:
        LocalCaseFileStore(tmp_path).get_text(doc.doc_id, doc.version_id, 0, 1)
    assert not isinstance(exc.value, legalai_contracts.DocumentNotFoundError)


# ---- AC2: original_sha256 is the hash of the original bytes ---------------------------------------------


def test_every_ingested_document_has_original_sha256(tmp_path: Path) -> None:
    store = LocalCaseFileStore(tmp_path)
    corpus = _corpus()
    for name, data in corpus.items():
        doc = store.ingest(CASE, name, data, received_at=T0, encoding=_encoding(name)).document
        expected = _sha(data)
        assert doc.original_sha256 == expected, name
        assert store.get_version(doc.doc_id, doc.version_id).original_sha256 == expected
        # content_sha256 covers the stored UTF-8 text (ADR-0007 §4.1). It equals original_sha256 only when
        # the file is UTF-8 text stored byte for byte; extracted or re-encoded formats must differ.
        text = store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
        assert doc.content_sha256 == _sha(text.encode("utf-8")), name
        if not name.endswith((".md", "催款函.txt")):
            assert doc.content_sha256 != expected, name
        # The stored original is byte-identical to what was received.
        version_dir = tmp_path / "casefile" / "cases" / CASE / doc.doc_id / doc.version_id
        assert _sha(next(version_dir.glob("original*")).read_bytes()) == expected
    fresh = LocalCaseFileStore(tmp_path)  # reload everything from disk
    listed = fresh.list_documents(CASE)
    assert len(listed) == len(corpus)
    assert sorted(d.original_sha256 or "" for d in listed) == sorted(_sha(d) for d in corpus.values())
    for doc in listed:
        assert fresh.get_document(doc.doc_id, doc.version_id).original_sha256 == doc.original_sha256


def test_reingest_keeps_hash_per_version(tmp_path: Path) -> None:
    store = LocalCaseFileStore(tmp_path)
    v1_bytes, v2_bytes = b"SYNTHETIC v1 ZZ.\n", b"SYNTHETIC v2 ZZ.\n"
    v1 = store.ingest(CASE, "SYNTHETIC.txt", v1_bytes, received_at=T0).document
    again = store.ingest(CASE, "SYNTHETIC.txt", v1_bytes, received_at=T0)
    assert not again.created and again.document.original_sha256 == _sha(v1_bytes)
    v2 = store.ingest(CASE, "SYNTHETIC.txt", v2_bytes, received_at=T0).document
    assert v2.original_sha256 == _sha(v2_bytes)
    assert store.get_document(v1.doc_id, v1.version_id).original_sha256 == _sha(v1_bytes)


# ---- records written before REQ-PMO-0013 (schema 1 and 2) -----------------------------------------------


@pytest.mark.parametrize("schema", [1, 2])
def test_legacy_record_reports_hash_recorded_at_intake_without_rewriting(tmp_path: Path, schema: int) -> None:
    data = build_pdf(zh_pages(), "SYNTHETIC contract")
    doc = LocalCaseFileStore(tmp_path).ingest(CASE, "SYNTHETIC-合同.pdf", data, received_at=T0).document

    def downgrade(meta: dict[str, Any]) -> None:
        # Exactly what the pre-REQ-PMO-0013 store wrote: no original_sha256 inside the CaseDocument.
        meta["schema"] = schema
        del meta["document"]["original_sha256"]
        if schema == 1:
            del meta["substitutions"]

    version_dir = _edit_meta(tmp_path, downgrade).parent
    before = {p.name: p.read_bytes() for p in version_dir.iterdir()}

    fresh = LocalCaseFileStore(tmp_path)
    legacy = fresh.get_document(doc.doc_id, doc.version_id)
    assert legacy.original_sha256 == _sha(data)
    assert legacy == doc  # identical to what a current intake reports
    assert fresh.list_documents(CASE) == [doc]
    assert fresh.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
    # Unchanged re-ingest of a legacy record also reports the hash.
    unchanged = fresh.ingest(CASE, "SYNTHETIC-合同.pdf", data, received_at=T0)
    assert not unchanged.created and unchanged.document.original_sha256 == _sha(data)
    # Reading never rewrites stored files (text, original or metadata).
    assert {p.name: p.read_bytes() for p in version_dir.iterdir()} == before


def test_schema_3_record_without_original_sha256_is_refused(tmp_path: Path) -> None:
    doc = LocalCaseFileStore(tmp_path).ingest(CASE, "SYNTHETIC.txt", TXT, received_at=T0).document
    _edit_meta(tmp_path, lambda meta: meta["document"].pop("original_sha256"))
    with pytest.raises(StoreIntegrityError) as exc:
        LocalCaseFileStore(tmp_path).get_document(doc.doc_id, doc.version_id)
    assert not isinstance(exc.value, legalai_contracts.DocumentNotFoundError)


@pytest.mark.parametrize("where", ["document", "provenance"])
def test_inconsistent_original_sha256_is_refused(tmp_path: Path, where: str) -> None:
    doc = LocalCaseFileStore(tmp_path).ingest(CASE, "SYNTHETIC.txt", TXT, received_at=T0).document
    forged = _sha(b"SYNTHETIC other bytes")

    def forge(meta: dict[str, Any]) -> None:
        if where == "document":
            meta["document"]["original_sha256"] = forged
        else:
            meta["original_sha256"] = forged

    _edit_meta(tmp_path, forge)
    with pytest.raises(StoreIntegrityError):
        LocalCaseFileStore(tmp_path).get_document(doc.doc_id, doc.version_id)


def test_legacy_record_with_malformed_provenance_hash_is_refused(tmp_path: Path) -> None:
    doc = LocalCaseFileStore(tmp_path).ingest(CASE, "SYNTHETIC.txt", TXT, received_at=T0).document

    def downgrade_and_corrupt(meta: dict[str, Any]) -> None:
        meta["schema"] = 2
        del meta["document"]["original_sha256"]
        meta["original_sha256"] = "not-a-sha256"

    _edit_meta(tmp_path, downgrade_and_corrupt)
    with pytest.raises(StoreIntegrityError):
        LocalCaseFileStore(tmp_path).get_document(doc.doc_id, doc.version_id)
