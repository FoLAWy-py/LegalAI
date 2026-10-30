# ruff: noqa: RUF001 - full-width CJK punctuation is the data under test, not a typo.
"""LocalCaseFileStore: intake of every format, exact ranges (AC3), versioning, integrity, logging (AC5)."""

import logging
import random
import re
import stat
import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import pytest

import legalai_casefile
from legalai_casefile import (
    DocumentNotFoundError,
    IntakeError,
    InvalidIdentifierError,
    InvalidRangeError,
    LocalCaseFileStore,
    ScannedDocumentError,
    StoreIntegrityError,
    derive_doc_id,
)
from legalai_casefile._pdf_corpus import ZH_PAGES, astral_pages, mixed_pages, zh_pages
from legalai_casefile._synthetic_docs import build_docx, para, table
from legalai_casefile._synthetic_pdf import FULL_PAGE_IMAGE, Page, build_pdf
from legalai_contracts import CaseDocument, CaseFileStore

T0 = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
CASE = "case-zz-0001"

ZH_TXT = "SYNTHETIC 催款函\r\n示例乙：贵方尚欠货款¥8,000.00（捌仟元整）。\r\n示例甲\r\n"
EN_TXT = "SYNTHETIC Demand Letter\nThe Buyer owes USD 1,000.00 under invoice ZZ-7.\n"
MIXED_MD = "# SYNTHETIC 备忘录 Memo\n\n甲方 (Party A) 同意 to extend；签字人 张𠀀。\n"
DOCX_TEXTS = (
    "SYNTHETIC 补充协议（ZZ）",
    "双方同意将交付期限延长至２０２６年１２月３１日。",
    "Signed by Party A / 甲方",
)


def _eml() -> bytes:
    msg = EmailMessage()
    msg["From"] = "示例甲 <a@example.zz>"
    msg["To"] = "b@example.zz"
    msg["Date"] = "Fri, 30 Oct 2026 09:00:00 +0800"
    msg["Subject"] = "SYNTHETIC 对账确认 statement"
    msg.set_content("截至２０２６年９月３０日，贵方欠款¥8,000.00。\nPlease confirm.\n", cte="base64")
    return msg.as_bytes()


def _all_formats() -> dict[str, bytes]:
    return {
        "SYNTHETIC-合同.pdf": build_pdf(zh_pages(), "SYNTHETIC contract"),
        "SYNTHETIC-receipt-mixed.pdf": build_pdf((*mixed_pages(), *astral_pages()), "SYNTHETIC receipt"),
        "SYNTHETIC-补充协议.docx": build_docx(
            "".join(para(t) for t in DOCX_TEXTS) + table([["项目", "Amount"], ["货款", "¥8,000.00"]])
        ),
        "SYNTHETIC-催款函.txt": ZH_TXT.encode(),
        "SYNTHETIC-demand.txt": EN_TXT.encode(),
        "SYNTHETIC-memo.md": MIXED_MD.encode(),
        "SYNTHETIC-对账.eml": _eml(),
    }


@pytest.fixture
def store(tmp_path: Path) -> LocalCaseFileStore:
    return LocalCaseFileStore(tmp_path)


def test_store_implements_port(store: LocalCaseFileStore) -> None:
    assert isinstance(store, CaseFileStore)
    assert "LocalCaseFileStore" in legalai_casefile.__all__


def test_every_format_ingests_with_metadata(store: LocalCaseFileStore) -> None:
    expected_lang = {
        "SYNTHETIC-合同.pdf": "zh",
        "SYNTHETIC-催款函.txt": "zh",
        "SYNTHETIC-demand.txt": "en",
        "SYNTHETIC-memo.md": "mul",
    }
    docs = {}
    for name, data in _all_formats().items():
        res = store.ingest(CASE, name, data, received_at=T0)
        assert res.created
        doc = res.document
        assert doc.title == name and "SYNTHETIC" in doc.title
        assert doc.case_id == CASE and doc.received_at == T0
        if name in expected_lang:
            assert doc.language == expected_lang[name], name
        docs[name] = doc
    assert docs["SYNTHETIC-合同.pdf"].media_type == "application/pdf"
    assert len(docs["SYNTHETIC-合同.pdf"].page_starts) == 3
    assert len(docs["SYNTHETIC-receipt-mixed.pdf"].page_starts) == 3
    assert docs["SYNTHETIC-对账.eml"].media_type == "message/rfc822"
    assert docs["SYNTHETIC-memo.md"].media_type == "text/markdown"
    for name in (
        "SYNTHETIC-补充协议.docx",
        "SYNTHETIC-催款函.txt",
        "SYNTHETIC-memo.md",
        "SYNTHETIC-对账.eml",
    ):
        assert docs[name].page_starts == (0,)
    listed = store.list_documents(CASE)
    assert sorted(d.doc_id for d in listed) == sorted(d.doc_id for d in docs.values())
    assert [d.doc_id for d in listed] == sorted(d.doc_id for d in listed)
    for doc in docs.values():
        assert store.get_document(doc.doc_id, doc.version_id) == doc


def test_stored_text_round_trips_exactly(store: LocalCaseFileStore, tmp_path: Path) -> None:
    txt = store.ingest(CASE, "SYNTHETIC.txt", ZH_TXT.encode(), received_at=T0).document
    assert store.get_text(txt.doc_id, txt.version_id, 0, txt.char_count) == ZH_TXT  # CRLF kept
    pdf = store.ingest(CASE, "SYNTHETIC.pdf", build_pdf(zh_pages(), "SYNTHETIC"), received_at=T0).document
    full = store.get_text(pdf.doc_id, pdf.version_id, 0, pdf.char_count)
    assert full == "".join("\n".join(p) + "\f" for p in ZH_PAGES)
    on_disk = next(tmp_path.glob(f"casefile/cases/{CASE}/{pdf.doc_id}/{pdf.version_id}/text.txt"))
    assert on_disk.read_bytes().decode("utf-8") == full


def test_get_text_equals_slice_for_random_ranges(store: LocalCaseFileStore) -> None:
    """Property test (AC3): for seeded random ranges, get_text == stored_text[a:b]."""
    rng = random.Random(20261030)
    docs = [store.ingest(CASE, n, d, received_at=T0).document for n, d in _all_formats().items()]
    for doc in docs:
        full = store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
        assert len(full) == doc.char_count
        for _ in range(300):
            a = rng.randint(0, doc.char_count)
            b = rng.randint(a, doc.char_count)
            assert store.get_text(doc.doc_id, doc.version_id, a, b) == full[a:b]
        # Edge ranges.
        assert store.get_text(doc.doc_id, doc.version_id, 0, 0) == ""
        assert store.get_text(doc.doc_id, doc.version_id, doc.char_count - 1, doc.char_count) == full[-1]


def test_offsets_are_code_points_for_astral_characters(store: LocalCaseFileStore) -> None:
    doc = store.ingest(CASE, "SYNTHETIC.md", MIXED_MD.encode(), received_at=T0).document
    at = MIXED_MD.index("𠀀")
    assert store.get_text(doc.doc_id, doc.version_id, at, at + 1) == "𠀀"


@pytest.mark.parametrize(("a", "b"), [(-1, 3), (0, 10_000), (5, 4), (True, 3), (0.0, 3)])
def test_invalid_ranges_raise_never_clamp(store: LocalCaseFileStore, a: object, b: object) -> None:
    doc = store.ingest(CASE, "SYNTHETIC.txt", EN_TXT.encode(), received_at=T0).document
    with pytest.raises(InvalidRangeError):
        store.get_text(doc.doc_id, doc.version_id, a, b)  # type: ignore[arg-type]


def test_reingest_changed_file_creates_new_version(store: LocalCaseFileStore) -> None:
    v1 = store.ingest(CASE, "SYNTHETIC-协议.txt", "第一版。\n".encode(), received_at=T0).document
    v2 = store.ingest(
        CASE, "SYNTHETIC-协议.txt", "第二版。\n".encode(), received_at=T0 + timedelta(days=1)
    ).document
    assert v1.doc_id == v2.doc_id and v1.version_id != v2.version_id
    assert store.get_text(v1.doc_id, v1.version_id, 0, v1.char_count) == "第一版。\n"
    assert store.get_text(v2.doc_id, v2.version_id, 0, v2.char_count) == "第二版。\n"
    assert store.list_documents(CASE) == [v2]
    assert [v.document for v in store.list_versions(v1.doc_id)] == [v1, v2]

    same = store.ingest(CASE, "SYNTHETIC-协议.txt", "第二版。\n".encode())
    assert not same.created and same.document == v2

    v3 = store.ingest(
        CASE, "SYNTHETIC-协议.txt", "第一版。\n".encode(), received_at=T0 + timedelta(days=2)
    ).document
    assert v3.version_id not in (v1.version_id, v2.version_id)
    assert store.list_documents(CASE) == [v3]
    assert store.get_document(v1.doc_id, v1.version_id) == v1


def test_provenance_recorded(store: LocalCaseFileStore) -> None:
    data = build_pdf(zh_pages(), "SYNTHETIC")
    doc = store.ingest(CASE, "SYNTHETIC-合同.pdf", data, received_at=T0).document
    stored = store.get_version(doc.doc_id, doc.version_id)
    assert stored.original_filename == "SYNTHETIC-合同.pdf"
    assert stored.original_size == len(data)
    assert stored.extractor.startswith("pypdf ")
    assert doc.version_id.endswith(stored.original_sha256[:12])


def test_refused_file_stores_nothing(store: LocalCaseFileStore, tmp_path: Path) -> None:
    with pytest.raises(ScannedDocumentError):
        store.ingest(CASE, "SYNTHETIC-scan.pdf", build_pdf([Page(images=(FULL_PAGE_IMAGE,))], "SYNTHETIC"))
    assert store.list_documents(CASE) == []
    assert not list(tmp_path.glob("casefile/cases/*/*/*"))


def test_tampered_text_is_refused(tmp_path: Path) -> None:
    doc = LocalCaseFileStore(tmp_path).ingest(CASE, "SYNTHETIC.txt", EN_TXT.encode(), received_at=T0).document
    path = next(tmp_path.glob("casefile/cases/*/*/*/text.txt"))
    path.chmod(0o600)
    path.write_bytes(EN_TXT.replace("1,000", "9,000").encode())
    with pytest.raises(StoreIntegrityError):
        LocalCaseFileStore(tmp_path).get_text(doc.doc_id, doc.version_id, 0, 5)


def test_unknown_documents(store: LocalCaseFileStore) -> None:
    with pytest.raises(DocumentNotFoundError):
        store.get_document("cf-missing", "v0001-000000000000")
    doc = store.ingest(CASE, "SYNTHETIC.txt", EN_TXT.encode(), received_at=T0).document
    with pytest.raises(DocumentNotFoundError):
        store.get_text(doc.doc_id, "v0009-000000000000", 0, 1)
    assert store.list_documents("case-unknown") == []


@pytest.mark.parametrize("bad", ["../escape", "a/b", "", ".hidden", "x" * 200, "案件1"])
def test_unsafe_identifiers_rejected(store: LocalCaseFileStore, bad: str) -> None:
    with pytest.raises(InvalidIdentifierError):
        store.ingest(bad, "SYNTHETIC.txt", EN_TXT.encode())
    with pytest.raises(InvalidIdentifierError):
        store.get_document(bad, "v1")


def test_doc_id_is_stable_across_unicode_normalisation() -> None:
    nfc = "SYNTHETIC-café合同.pdf"
    assert derive_doc_id(CASE, nfc) == derive_doc_id(CASE, unicodedata.normalize("NFD", nfc))
    assert derive_doc_id(CASE, nfc) == derive_doc_id(CASE, f"/some/dir/{nfc}")
    assert derive_doc_id(CASE, nfc) != derive_doc_id("case-other", nfc)


def test_doc_id_cannot_cross_cases(store: LocalCaseFileStore) -> None:
    store.ingest(CASE, "SYNTHETIC.txt", EN_TXT.encode(), doc_id="shared-id")
    with pytest.raises(InvalidIdentifierError):
        store.ingest("case-zz-0002", "SYNTHETIC.txt", EN_TXT.encode(), doc_id="shared-id")


def test_naive_received_at_rejected(store: LocalCaseFileStore) -> None:
    with pytest.raises(ValueError, match="timezone"):
        store.ingest(CASE, "SYNTHETIC.txt", EN_TXT.encode(), received_at=datetime(2026, 10, 30))


def test_files_are_private(store: LocalCaseFileStore, tmp_path: Path) -> None:
    store.ingest(CASE, "SYNTHETIC.txt", EN_TXT.encode(), received_at=T0)
    version_dir = next(tmp_path.glob("casefile/cases/*/*/*"))
    assert stat.S_IMODE(version_dir.stat().st_mode) == 0o700
    for f in version_dir.iterdir():
        assert stat.S_IMODE(f.stat().st_mode) == 0o600


def test_ingest_file_reads_path(store: LocalCaseFileStore, tmp_path: Path) -> None:
    src = tmp_path / "SYNTHETIC-来函.txt"
    src.write_bytes(ZH_TXT.encode())
    doc = store.ingest_file(CASE, src, received_at=T0).document
    assert doc.title == "SYNTHETIC-来函.txt"
    assert doc.doc_id == derive_doc_id(CASE, "SYNTHETIC-来函.txt")


def test_data_dir_must_exist(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        LocalCaseFileStore(tmp_path / "missing")


def test_no_environment_variables_are_read(
    store: LocalCaseFileStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    monkeypatch.setenv("LEGALAI_DATA_DIR", str(decoy))
    store.ingest(CASE, "SYNTHETIC.txt", EN_TXT.encode(), received_at=T0)
    assert not any(decoy.iterdir())
    src = Path(legalai_casefile.__file__).parent
    for py in src.glob("*.py"):
        code = py.read_text(encoding="utf-8")
        assert not re.search(r"\bos\.environ\b|\bgetenv\b|\bimport\s+environ\b|environb", code), py.name


def test_casedocument_contract_holds(store: LocalCaseFileStore) -> None:
    for name, data in _all_formats().items():
        doc = store.ingest(CASE, name, data, received_at=T0).document
        assert CaseDocument.model_validate(doc.model_dump()) == doc
        assert doc.page_of(0) == 1 and doc.page_of(doc.char_count - 1) == len(doc.page_starts)


def test_no_document_text_in_logs_at_info_or_above(
    store: LocalCaseFileStore, caplog: pytest.LogCaptureFixture
) -> None:
    """AC5: ingest every format, refuse some, read ranges; no record at INFO+ contains document text."""
    caplog.set_level(logging.DEBUG)
    formats = _all_formats()
    for name, data in formats.items():
        doc = store.ingest(CASE, name, data, received_at=T0).document
        store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
        store.ingest(CASE, name, data)  # unchanged path logs too
    refused = {
        "SYNTHETIC-scan.pdf": build_pdf([zh_pages()[0], Page(images=(FULL_PAGE_IMAGE,))], "SYNTHETIC"),
        "SYNTHETIC-nomap.pdf": build_pdf(zh_pages(), "SYNTHETIC", to_unicode=False),
        "SYNTHETIC-gbk.txt": ZH_TXT.encode("gb18030"),
    }
    for name, data in refused.items():
        with pytest.raises(IntakeError) as err:
            store.ingest(CASE, name, data)
        assert "示例" not in str(err.value)

    assert caplog.records, "intake must log metadata"
    assert any(r.name.startswith("legalai_casefile") and r.levelno == logging.INFO for r in caplog.records)
    assert not _leaks(r for r in caplog.records if r.levelno >= logging.INFO)
    # Our own logger stays text-free at every level.
    assert not _leaks(r for r in caplog.records if r.name.startswith("legalai_casefile"))


_FRAGMENTS = {
    f
    for f in {ln[i : i + 4] for page in ZH_PAGES for ln in page for i in range(0, max(len(ln) - 4, 1), 3)}
    | {t[:8] for t in DOCX_TEXTS}
    | {"贵方尚欠", "捌仟元", "欠款", "备忘录", "张𠀀"}
    if f.strip() and not f.isascii()
} | {"Buyer owes", "Party A", "Please confirm"}


def _leaks(records: Iterable[logging.LogRecord]) -> list[str]:
    return [r.name for r in records if any(f in r.getMessage() for f in _FRAGMENTS)]


def test_leak_detector_is_not_vacuous() -> None:
    planted = logging.LogRecord("planted", logging.INFO, __file__, 1, "got %s", (ZH_PAGES[1][0],), None)
    assert _leaks([planted]) == ["planted"]
