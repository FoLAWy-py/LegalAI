"""Compare candidate PDF text extractors on synthetic Chinese / mixed zh-en PDFs (REQ-PMO-0001 §6).

Run from the repo root (candidates are installed ephemerally, not added to the project):

    uv run --with pypdf --with pdfminer.six --with pypdfium2 --with pymupdf \
        python departments/casefile/tools/compare_pdf_extractors.py

For each fixture of `legalai_casefile._pdf_corpus` and each library, the cell shows:
- N: extracted text equals the truth after deleting all whitespace (no loss, no extra characters,
  correct reading order) - the hard requirement;
- L: the non-empty, stripped lines equal the truth lines (also catches spaces inserted inside
  Chinese text, which break exact-quote matching);
- P: page count is correct.
Capital = pass, lower case = fail. Negative fixtures show what each library returns, so silent
failures are visible. All fixture text is synthetic (jurisdiction ZZ).
"""

import importlib.metadata
import io
import re
import sys
from collections.abc import Callable

from legalai_casefile._pdf_corpus import corpus, zh_pages
from legalai_casefile._synthetic_pdf import FULL_PAGE_IMAGE, Page, build_pdf


def ex_pypdf(data: bytes) -> list[str]:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        reader.decrypt("")
    return [p.extract_text() for p in reader.pages]


def ex_pdfminer(data: bytes) -> list[str]:
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTTextContainer

    return [
        "".join(el.get_text() for el in layout if isinstance(el, LTTextContainer))
        for layout in extract_pages(io.BytesIO(data))
    ]


def ex_pypdfium2(data: bytes) -> list[str]:
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    return [doc[i].get_textpage().get_text_range() for i in range(len(doc))]


def ex_pymupdf(data: bytes) -> list[str]:
    import pymupdf

    return [page.get_text() for page in pymupdf.open(stream=data, filetype="pdf")]


CANDIDATES: dict[str, tuple[str, Callable[[bytes], list[str]]]] = {
    "pypdf": ("pypdf", ex_pypdf),
    "pdfminer.six": ("pdfminer.six", ex_pdfminer),
    "pypdfium2": ("pypdfium2", ex_pypdfium2),
    "pymupdf": ("pymupdf", ex_pymupdf),
}


def _license(dist: str) -> str:
    meta = importlib.metadata.metadata(dist)
    lic = meta.get("License-Expression") or meta.get("License") or ""
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or [] if "License" in c]
    return (lic.splitlines()[0][:70] if lic else "") + (f" {classifiers}" if classifiers else "")


def score(pages_out: list[str], truth: tuple[tuple[str, ...], ...]) -> str:
    def nows(s: str) -> str:
        return re.sub(r"\s+", "", s)

    nonws = nows("".join(pages_out)) == nows("".join("".join(p) for p in truth))
    lines = [tuple(ln.strip() for ln in p.splitlines() if ln.strip()) for p in pages_out] == list(truth)
    pages = len(pages_out) == len(truth)
    return ("N" if nonws else "n") + ("L" if lines else "l") + ("P" if pages else "p")


def main() -> int:
    available = {}
    for name, (dist, fn) in CANDIDATES.items():
        try:
            version = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            print(f"{name:13} not installed - skipped")
            continue
        available[name] = fn
        print(f"{name:13} {version:10} license: {_license(dist)}")
    print()
    fixtures = corpus()
    header = f"{'fixture':26}" + "".join(f"{n:>14}" for n in available)
    print(header + "\n" + "-" * len(header))
    totals = dict.fromkeys(available, 0)
    for fx in fixtures:
        data = build_pdf(fx.pages, f"SYNTHETIC {fx.name}")
        row = f"{fx.name:26}"
        for name, fn in available.items():
            try:
                cell = score(fn(data), fx.truth)
            except Exception as exc:  # noqa: BLE001 - comparison tool reports any failure as a cell
                cell = f"ERR:{type(exc).__name__}"[:13]
            totals[name] += cell == "NLP"
            row += f"{cell:>14}"
        print(row)
    print(f"\nall-pass (NLP) totals of {len(fixtures)}: {totals}")

    one = zh_pages()
    negatives = {
        "no_tounicode": build_pdf(one[:1], "SYNTHETIC no ToUnicode", to_unicode=False),
        "image_only_page2": build_pdf([one[0], Page(images=(FULL_PAGE_IMAGE,)), one[2]], "SYNTHETIC scan"),
        "encrypted_empty_pw": build_pdf(one[:1], "SYNTHETIC enc", user_password=""),
        "encrypted_pw": build_pdf(one[:1], "SYNTHETIC enc", user_password="secret"),
    }
    print("\nNegative fixtures (first 20 chars of each page, or the exception):")
    for fixture, data in negatives.items():
        for name, fn in available.items():
            try:
                print(f"  {fixture:19} {name:13} -> {[s[:20] for s in fn(data)]!r}")
            except Exception as exc:  # noqa: BLE001 - report
                print(f"  {fixture:19} {name:13} -> raises {type(exc).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
