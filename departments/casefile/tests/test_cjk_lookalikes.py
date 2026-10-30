"""REQ-PMO-0009: CJK look-alike code points from PDF font maps.

The external fixture was produced by macOS `cupsfilter` (text -> PDF, embedded PingFang SC subset) from
synthetic ZZ text; regenerate with `tools/make_external_fixtures.py`. Page truth comes from macOS PDFKit
(`*.pages.json`), not from pypdf.
"""

import io
import json
import logging
import unicodedata
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

import pypdf
import pytest

from legalai_casefile import (
    CJK_MAPPING_VERSION,
    PAGE_TERMINATOR,
    CasefileError,
    LocalCaseFileStore,
    PartialExtractionError,
    StoreIntegrityError,
    extract_document,
    restore_extracted_text,
)
from legalai_casefile._cjk import RADICAL_BLOCKS, TABLE_FILE, radical_table
from legalai_casefile._synthetic_docs import build_docx, para
from legalai_casefile._synthetic_pdf import Page, build_pdf, line

FIXTURES = Path(__file__).parent / "fixtures" / "external"
PDF = FIXTURES / "zz-radicals-cupsfilter.pdf"
SOURCE = (FIXTURES / "zz-radicals-source.txt").read_text(encoding="utf-8").splitlines()
TRUTH = json.loads((FIXTURES / "zz-radicals-cupsfilter.pages.json").read_text(encoding="utf-8"))
T0 = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
CASE = "case-zz-0009"
RADICAL_MAN, IDEOGRAPH_REN = "⼈", "人"
RADICAL_SEE, IDEOGRAPH_JIAN = "⻅", "见"
RADICAL_REPEAT = "⺀"
COMPAT_KAI = "豈"


def _pypdf_raw(data: bytes) -> str:
    """What pypdf itself returns, assembled the way `_pdf.py` assembles pages."""
    reader = pypdf.PdfReader(io.BytesIO(data), strict=True)
    return "".join(p.extract_text() + PAGE_TERMINATOR for p in reader.pages)


# ---- the external fixture ---------------------------------------------------------------------------


def test_fixture_is_external_with_embedded_subset_font() -> None:
    reader = pypdf.PdfReader(io.BytesIO(PDF.read_bytes()))
    assert "Quartz PDFContext" in str(reader.metadata.get("/Producer"))
    embedded = []
    for page in reader.pages:
        for ref in page["/Resources"]["/Font"].values():
            font = ref.get_object()
            desc = font.get("/FontDescriptor")
            desc = desc.get_object() if desc is not None else {}
            if any(k in desc for k in ("/FontFile", "/FontFile2", "/FontFile3")):
                embedded.append(str(font["/BaseFont"]))
    assert any("+PingFang" in name for name in embedded), embedded  # "ABCDEF+" prefix = subset
    raw = _pypdf_raw(PDF.read_bytes())
    assert sum(1 for c in raw if any(lo <= ord(c) <= hi for lo, hi in RADICAL_BLOCKS)) == 664
    assert not any(ln in raw for ln in SOURCE[1:])  # the defect: no numbered line survives as-is


def test_all_source_lines_found_exactly_after_mapping() -> None:
    data = PDF.read_bytes()
    ex = extract_document("SYNTHETIC-radicals.pdf", data)
    assert [ln for ln in SOURCE if ln not in ex.text] == []
    raw = _pypdf_raw(data)
    assert len(ex.text) == len(raw)
    assert restore_extracted_text(ex.text, ex.substitutions) == raw
    assert len(ex.substitutions) == 664 and ex.substitution_table == CJK_MAPPING_VERSION
    assert not any(any(lo <= ord(c) <= hi for lo, hi in RADICAL_BLOCKS) for c in ex.text)


def test_warning_names_count_and_code_points_without_text() -> None:
    ex = extract_document("SYNTHETIC-radicals.pdf", PDF.read_bytes())
    (warning,) = [w for w in ex.warnings if "radical" in w]
    assert "664" in warning
    assert "U+2F08->U+4EBA x119" in warning and "U+2EC5->U+89C1 x20" in warning
    assert warning.isascii()  # code points only, never document characters


def test_page_of_against_independent_pdfkit_truth(tmp_path: Path) -> None:
    store = LocalCaseFileStore(tmp_path)
    doc = store.ingest(CASE, "SYNTHETIC-radicals.pdf", PDF.read_bytes(), received_at=T0).document
    text = store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
    assert len(doc.page_starts) == len(TRUTH["pages"])
    by_number = {int(ln[1:4]): ln for ln in SOURCE[1:]}
    checked_pages = set()
    for page in TRUTH["pages"]:
        expected = page["page"]
        lines = [by_number[n] for n in page["line_numbers"]] + ([SOURCE[0]] if page["has_title"] else [])
        assert lines
        for ln in lines:
            at = text.index(ln)
            for off in (at, at + len(ln) // 2, at + len(ln) - 1):
                assert doc.page_of(off) == expected, (ln[:4], off)
        checked_pages.add(expected)
    assert checked_pages == set(range(1, len(doc.page_starts) + 1))
    assert sum(len(p["line_numbers"]) for p in TRUTH["pages"]) == len(SOURCE) - 1


def test_store_keeps_reversible_record(tmp_path: Path) -> None:
    data = PDF.read_bytes()
    doc = LocalCaseFileStore(tmp_path).ingest(CASE, "SYNTHETIC-radicals.pdf", data, received_at=T0).document
    fresh = LocalCaseFileStore(tmp_path)  # reload everything from disk
    stored = fresh.get_version(doc.doc_id, doc.version_id)
    assert len(stored.substitutions) == 664 and stored.substitution_table == CJK_MAPPING_VERSION
    assert fresh.get_extracted_text(doc.doc_id, doc.version_id) == _pypdf_raw(data)
    meta = json.loads(next(tmp_path.glob("casefile/cases/*/*/*/meta.json")).read_text(encoding="utf-8"))
    assert meta["schema"] == 3  # 3 since REQ-PMO-0013 (CaseDocument.original_sha256 stored)
    assert meta["substitutions"]["table"] == CJK_MAPPING_VERSION
    stored_text = fresh.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
    raw = _pypdf_raw(data)
    positions = meta["substitutions"]["positions"]
    assert len(positions) == 664
    for offset, original, replacement in positions:
        assert raw[offset] == chr(int(original, 16)) and stored_text[offset] == chr(int(replacement, 16))
    # Outside the recorded positions the stored text is byte-for-byte the extractor's output.
    recorded = {p[0] for p in positions}
    assert all(a == b for i, (a, b) in enumerate(zip(raw, stored_text, strict=True)) if i not in recorded)


def test_tampered_substitution_record_is_refused(tmp_path: Path) -> None:
    store = LocalCaseFileStore(tmp_path)
    doc = store.ingest(CASE, "SYNTHETIC-radicals.pdf", PDF.read_bytes(), received_at=T0).document
    meta_path = next(tmp_path.glob("casefile/cases/*/*/*/meta.json"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["substitutions"]["positions"][0][0] += 1  # point the record at the wrong character
    meta_path.chmod(0o600)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(StoreIntegrityError):
        LocalCaseFileStore(tmp_path).get_extracted_text(doc.doc_id, doc.version_id)


def test_no_document_text_in_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    store = LocalCaseFileStore(tmp_path)
    doc = store.ingest(CASE, "SYNTHETIC-radicals.pdf", PDF.read_bytes(), received_at=T0).document
    store.get_extracted_text(doc.doc_id, doc.version_id)
    fragments = {ln[i : i + 3] for ln in SOURCE for i in range(0, len(ln) - 3, 2)}
    fragments = {f for f in fragments if not f.isascii()}
    assert any(r.name.startswith("legalai_casefile") for r in caplog.records)
    for record in caplog.records:
        if record.levelno >= logging.INFO or record.name.startswith("legalai_casefile"):
            assert not any(f in record.getMessage() for f in fragments), record.name


# ---- mapping applies only where the extractor is the source -------------------------------------------


GENUINE = (
    f"SYNTHETIC 部首说明：{RADICAL_MAN}（部首）与{IDEOGRAPH_REN}不同；{RADICAL_SEE}、{COMPAT_KAI}保持原样。\n"
)


@pytest.mark.parametrize("name", ["SYNTHETIC.txt", "SYNTHETIC.md"])
def test_genuine_radicals_in_text_files_are_unchanged(name: str, tmp_path: Path) -> None:
    store = LocalCaseFileStore(tmp_path)
    res = store.ingest(CASE, name, GENUINE.encode(), received_at=T0)
    doc = res.document
    assert store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count) == GENUINE
    assert res.warnings == ()
    assert store.get_version(doc.doc_id, doc.version_id).substitutions == ()


def test_genuine_radicals_in_docx_and_eml_are_unchanged() -> None:
    assert extract_document("SYNTHETIC.docx", build_docx(para(GENUINE.rstrip("\n")))).text == GENUINE
    msg = EmailMessage()
    msg["From"] = "a@example.zz"
    msg["Date"] = "Fri, 30 Oct 2026 09:00:00 +0800"
    msg.set_content(GENUINE)
    ex = extract_document("SYNTHETIC.eml", msg.as_bytes())
    assert ex.text.endswith(GENUINE) and ex.substitutions == ()


def test_textutil_docx_from_same_source_is_exact() -> None:
    """Evidence for §6: the DOCX path needs no mapping (the author's code points are stored as typed)."""
    ex = extract_document("SYNTHETIC.docx", (FIXTURES / "zz-radicals-textutil.docx").read_bytes())
    assert ex.text == "\n".join(SOURCE) + "\n"


# ---- in-package PDFs whose ToUnicode names radicals ----------------------------------------------------


def test_synthetic_pdf_radicals_are_mapped_and_recorded() -> None:
    truth = f"借款{IDEOGRAPH_REN}应当遵守约定；证{IDEOGRAPH_JIAN}如下。"
    as_written = truth.replace(IDEOGRAPH_REN, RADICAL_MAN).replace(IDEOGRAPH_JIAN, RADICAL_SEE)
    data = build_pdf([Page(lines=(line(as_written, 72, 770),))], "SYNTHETIC radicals")
    ex = extract_document("SYNTHETIC.pdf", data)
    assert ex.text == truth + PAGE_TERMINATOR
    assert [(s.offset, s.original, s.replacement) for s in ex.substitutions] == [
        (truth.index(IDEOGRAPH_REN), RADICAL_MAN, IDEOGRAPH_REN),
        (truth.index(IDEOGRAPH_JIAN), RADICAL_SEE, IDEOGRAPH_JIAN),
    ]


def test_radical_without_equivalent_is_refused() -> None:
    pages = [
        Page(lines=(line("第一页正常。", 72, 770),)),
        Page(lines=(line(f"重复符号{RADICAL_REPEAT}。", 72, 770),)),
    ]
    with pytest.raises(PartialExtractionError) as err:
        extract_document("SYNTHETIC.pdf", build_pdf(pages, "SYNTHETIC"))
    assert err.value.pages == (2,)
    assert "U+2E80 x1" in str(err.value)
    assert str(err.value).isascii()


def test_compatibility_ideographs_are_kept_with_warning() -> None:
    text = f"示例{COMPAT_KAI}字。"
    ex = extract_document("SYNTHETIC.pdf", build_pdf([Page(lines=(line(text, 72, 770),))], "SYNTHETIC"))
    assert ex.text == text + PAGE_TERMINATOR
    assert ex.substitutions == ()
    (warning,) = [w for w in ex.warnings if "compatibility" in w]
    assert "U+F900 x1" in warning


# ---- the mapping table itself -------------------------------------------------------------------------


def test_table_is_complete_one_to_one_and_agrees_with_nfkc() -> None:
    table = radical_table()
    assigned = [
        chr(cp)
        for lo, hi in RADICAL_BLOCKS
        for cp in range(lo, hi + 1)
        if unicodedata.category(chr(cp)) != "Cn"
    ]
    assert sorted(set(assigned) - set(table)) == [RADICAL_REPEAT]  # the only radical with no equivalent
    assert len(table) == 328
    for radical, ideograph in table.items():
        assert len(ideograph) == 1 and unicodedata.name(ideograph).startswith("CJK UNIFIED IDEOGRAPH")
        if 0x2F00 <= ord(radical) <= 0x2FDF:  # Kangxi radicals: independent check against NFKC
            assert unicodedata.normalize("NFKC", radical) == ideograph
    assert unicodedata.unidata_version == "15.1.0" == TABLE_FILE.split("-")[1].removesuffix(".txt")


def test_table_hash_is_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    import legalai_casefile._cjk as cjk

    radical_table.cache_clear()
    monkeypatch.setattr(cjk, "TABLE_SHA256", "0" * 64)
    try:
        with pytest.raises(CasefileError):
            radical_table()
    finally:
        radical_table.cache_clear()
