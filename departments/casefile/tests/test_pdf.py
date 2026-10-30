# ruff: noqa: RUF001 - full-width CJK punctuation is the data under test, not a typo.
"""PDF intake: exact Chinese / mixed text, page mapping (AC2), scanned and partial rejection (AC4)."""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from legalai_casefile import (
    PAGE_TERMINATOR,
    CorruptDocumentError,
    EncryptedDocumentError,
    FormatMismatchError,
    IntakeReason,
    LocalCaseFileStore,
    PartialExtractionError,
    ScannedDocumentError,
    UnsupportedContentError,
    extract_document,
)
from legalai_casefile._pdf_corpus import ZH_PAGES, Fixture, corpus, mixed_pages, zh_pages
from legalai_casefile._synthetic_pdf import FULL_PAGE_IMAGE, Page, build_pdf, line

RECEIVED = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
FIXTURES = {fx.name: fx for fx in corpus()}
# Fixtures on which the chosen extractor (pypdf) reproduces every line exactly (REQ-PMO-0001 §8).
EXACT = [
    "zh_tj_3pages",
    "zh_glyph_positioned",
    "zh_kerned_small(-60)",
    "zh_char_spacing(Tc=3)",
    "mixed_zh_en_fonts",
    "zh_two_column",
    "zh_table_rows",
    "zh_astral_ext_b",
]


def _pages_of(text: str) -> list[str]:
    assert text.endswith(PAGE_TERMINATOR)
    return text.split(PAGE_TERMINATOR)[:-1]


@pytest.mark.parametrize("name", EXACT)
def test_page_text_is_exact(name: str) -> None:
    fx = FIXTURES[name]
    ex = extract_document("SYNTHETIC.pdf", build_pdf(fx.pages, f"SYNTHETIC {name}"))
    assert [p.split("\n") for p in _pages_of(ex.text)] == [list(t) for t in fx.truth]
    assert len(ex.page_starts) == len(fx.truth)
    assert ex.media_type == "application/pdf"
    assert ex.extractor.startswith("pypdf ")


def test_three_page_chinese_contract_full_text() -> None:
    ex = extract_document("SYNTHETIC.pdf", build_pdf(zh_pages(), "SYNTHETIC contract"))
    assert ex.text == "".join("\n".join(p) + "\f" for p in ZH_PAGES)
    # Full-width punctuation and digits survive unchanged.
    for ch in "（）：；“”《》【】！？、，。　２０¥":
        assert ch in ex.text


def test_known_limitations_lose_no_characters() -> None:
    """Reversed stream order and wide justification: line order / spacing differ, characters don't."""
    for name in ("zh_reverse_stream_order", "zh_kerned_wide(-250)"):
        fx = FIXTURES[name]
        ex = extract_document("SYNTHETIC.pdf", build_pdf(fx.pages, "SYNTHETIC"))
        got = sorted(re.sub(r"\s", "", ex.text))
        assert got == sorted(re.sub(r"\s", "", "".join("".join(p) for p in fx.truth))), name


def _multi_page_fixtures() -> list[Fixture]:
    blankish = (*zh_pages(), Page(), *mixed_pages(), *zh_pages("glyphs"))
    truth = (*ZH_PAGES, (), *FIXTURES["mixed_zh_en_fonts"].truth, *ZH_PAGES)
    return [
        FIXTURES["zh_tj_3pages"],
        FIXTURES["zh_glyph_positioned"],
        FIXTURES["mixed_zh_en_fonts"],
        Fixture("nine_pages_with_blank_page_4", blankish, truth),
    ]


@pytest.mark.parametrize("fx", _multi_page_fixtures(), ids=lambda f: f.name)
def test_page_of_matches_true_page_on_every_page(fx: Fixture, tmp_path: Path) -> None:
    store = LocalCaseFileStore(tmp_path)
    res = store.ingest(
        "case-zz-1", "SYNTHETIC-multi.pdf", build_pdf(fx.pages, "SYNTHETIC"), received_at=RECEIVED
    )
    doc = res.document
    text = store.get_text(doc.doc_id, doc.version_id, 0, doc.char_count)
    assert len(doc.page_starts) == len(fx.truth)
    sampled_pages = set()
    for page_no, lines in enumerate(fx.truth, start=1):
        start = doc.page_starts[page_no - 1]
        end = doc.page_starts[page_no] if page_no < len(doc.page_starts) else doc.char_count
        # The page terminator belongs to its page.
        assert text[end - 1] == PAGE_TERMINATOR and doc.page_of(end - 1) == page_no
        assert doc.page_of(start) == page_no
        cursor = start
        for ln in lines:
            at = text.index(ln, cursor)
            assert at < end, "line found on the wrong page"
            for off in (at, at + len(ln) // 2, at + len(ln) - 1):
                assert doc.page_of(off) == page_no
                assert text[off] == ln[off - at]
            cursor = at + len(ln)
        sampled_pages.add(page_no)
    assert sampled_pages == set(range(1, len(fx.truth) + 1))


def test_scanned_pdf_is_rejected_with_documented_error() -> None:
    data = build_pdf([Page(images=(FULL_PAGE_IMAGE,)), Page(images=(FULL_PAGE_IMAGE,))], "SYNTHETIC scan")
    with pytest.raises(ScannedDocumentError) as err:
        extract_document("SYNTHETIC-scan.pdf", data)
    assert err.value.reason is IntakeReason.SCANNED
    assert err.value.pages == (1, 2)
    assert "OCR is not supported" in str(err.value)


def test_one_scanned_page_rejects_whole_document() -> None:
    pages = zh_pages()
    data = build_pdf([pages[0], Page(images=(FULL_PAGE_IMAGE,)), pages[2]], "SYNTHETIC")
    with pytest.raises(ScannedDocumentError) as err:
        extract_document("SYNTHETIC.pdf", data)
    assert err.value.pages == (2,)


def test_invisible_ocr_text_layer_is_rejected() -> None:
    page = Page(lines=(line("识别文字层", 72, 700, render_mode=3),), images=(FULL_PAGE_IMAGE,))
    with pytest.raises(ScannedDocumentError) as err:
        extract_document("SYNTHETIC.pdf", build_pdf([page], "SYNTHETIC ocr"))
    assert err.value.pages == (1,)


@pytest.mark.parametrize("password", ["", "SYNTHETIC-pw"])
def test_encrypted_pdf_is_rejected_even_with_empty_password(password: str) -> None:
    data = build_pdf(zh_pages(), "SYNTHETIC enc", user_password=password)
    with pytest.raises(EncryptedDocumentError):
        extract_document("SYNTHETIC.pdf", data)


def test_font_without_unicode_map_is_partial_not_garbage() -> None:
    with pytest.raises(PartialExtractionError) as err:
        extract_document("SYNTHETIC.pdf", build_pdf(zh_pages(), "SYNTHETIC", to_unicode=False))
    assert err.value.pages == (1, 2, 3)
    assert "Unicode mapping" in str(err.value)


def test_large_image_on_text_page_is_partial() -> None:
    page = Page(lines=zh_pages()[0].lines, images=((0, 0, 400, 400),))
    with pytest.raises(PartialExtractionError) as err:
        extract_document("SYNTHETIC.pdf", build_pdf([page], "SYNTHETIC"))
    assert err.value.pages == (1,)


def test_graphics_without_text_is_partial() -> None:
    data = build_pdf([zh_pages()[0], Page(path=True)], "SYNTHETIC")
    with pytest.raises(PartialExtractionError) as err:
        extract_document("SYNTHETIC.pdf", data)
    assert err.value.pages == (2,)


def test_small_image_is_a_warning_not_text() -> None:
    page = Page(lines=zh_pages()[0].lines, images=((420, 80, 60, 60),))  # e.g. a seal
    ex = extract_document("SYNTHETIC.pdf", build_pdf([page], "SYNTHETIC"))
    assert ex.text == "\n".join(ZH_PAGES[0]) + "\f"
    assert any("image" in w for w in ex.warnings)


def test_blank_page_is_kept_as_its_own_page() -> None:
    ex = extract_document("SYNTHETIC.pdf", build_pdf([zh_pages()[0], Page(), zh_pages()[1]], "SYNTHETIC"))
    assert _pages_of(ex.text)[1] == ""
    assert len(ex.page_starts) == 3
    assert any("blank" in w for w in ex.warnings)


def test_truncated_pdf_is_corrupt() -> None:
    data = build_pdf(zh_pages(), "SYNTHETIC")
    with pytest.raises(CorruptDocumentError):
        extract_document("SYNTHETIC.pdf", data[: len(data) // 2])


def test_non_pdf_bytes_with_pdf_extension() -> None:
    with pytest.raises(FormatMismatchError):
        extract_document("SYNTHETIC.pdf", "这不是PDF".encode())


def test_hidden_layers_are_unsupported() -> None:
    data = build_pdf(zh_pages()[:1], "SYNTHETIC")
    # Add an optional-content configuration with a layer switched off by default.
    data = data.replace(
        b"<< /Type /Catalog /Pages",
        b"<< /OCProperties << /OCGs [] /D << /OFF [2 0 R] >> >> /Type /Catalog /Pages",
    )
    data = _fix_xref(data)
    with pytest.raises(UnsupportedContentError):
        extract_document("SYNTHETIC.pdf", data)


def _fix_xref(data: bytes) -> bytes:
    """Rebuild the xref table after an in-place edit of a synthetic PDF."""
    body, _, _ = data.partition(b"xref\n")
    offsets = [m.start() for m in re.finditer(rb"(?m)^\d+ 0 obj\n", body)]
    trailer = re.search(rb"trailer\n(<<.*?>>)\nstartxref", data, re.DOTALL)
    assert trailer is not None
    xref = f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode()
    xref += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return (
        body
        + xref
        + b"trailer\n"
        + trailer.group(1)
        + b"\nstartxref\n"
        + str(len(body)).encode()
        + b"\n%%EOF\n"
    )


def test_errors_never_contain_document_text() -> None:
    cases = [
        build_pdf(zh_pages(), "SYNTHETIC", to_unicode=False),
        build_pdf([zh_pages()[0], Page(images=(FULL_PAGE_IMAGE,))], "SYNTHETIC"),
        build_pdf([Page(lines=zh_pages()[0].lines, images=((0, 0, 500, 500),))], "SYNTHETIC"),
    ]
    fragments = [ln[:6] for page in ZH_PAGES for ln in page] + ["示例", "合同"]
    for data in cases:
        with pytest.raises((PartialExtractionError, ScannedDocumentError)) as err:
            extract_document("SYNTHETIC.pdf", data)
        assert not any(f in str(err.value) for f in fragments)
