"""Format dispatch: bytes + filename -> exact text with page boundaries, or a typed `IntakeError`."""

from pathlib import PurePath

from legalai_casefile._common import PAGE_TERMINATOR, Extraction
from legalai_casefile._docx import extract_docx
from legalai_casefile._eml import extract_eml
from legalai_casefile._pdf import extract_pdf
from legalai_casefile._text import extract_text_file
from legalai_casefile.errors import TooLargeError, UnsupportedFormatError

SUPPORTED_EXTENSIONS = (".docx", ".eml", ".md", ".pdf", ".txt")
DEFAULT_MAX_BYTES = 100 * 1024 * 1024


def extract_document(
    filename: str,
    data: bytes,
    *,
    encoding: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> Extraction:
    """Extract the exact text of one file.

    Guarantees: the returned text is exactly what the format's extractor produced, with no
    normalisation except the documented rules of each format (PDF pages each end with
    `PAGE_TERMINATOR`; text files lose only a byte-order mark). `page_starts[i]` is the code-point
    offset of page i+1; non-paginated formats have one page. Anything that would make the text
    incomplete or ambiguous raises an `IntakeError` subclass instead. `encoding` applies to .txt/.md.
    """
    if len(data) > max_bytes:
        raise TooLargeError(f"file is larger than {max_bytes} bytes")
    suffix = PurePath(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"extension {suffix or '(none)'!r} is not supported; use {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    if suffix == ".pdf":
        return extract_pdf(data)
    if suffix == ".docx":
        return extract_docx(data)
    if suffix == ".eml":
        return extract_eml(data)
    return extract_text_file(data, suffix, encoding)


__all__ = ["DEFAULT_MAX_BYTES", "PAGE_TERMINATOR", "SUPPORTED_EXTENSIONS", "Extraction", "extract_document"]
