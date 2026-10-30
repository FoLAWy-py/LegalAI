"""Local, versioned case-file storage under `<data_dir>/casefile/` and the `CaseFileStore` port.

Layout (one directory per version, written atomically, never modified afterwards):

    <data_dir>/casefile/cases/<case_id>/<doc_id>/<version_id>/
        original<.ext>   the file exactly as received
        text.txt         the extracted text, UTF-8, exactly the characters offsets refer to
        meta.json        CaseDocument + provenance (original filename, original SHA-256, extractor)

Hashes (ADR-0007 §4): `CaseDocument.content_sha256` is the SHA-256 of `text.txt` (the UTF-8 stored text);
`CaseDocument.original_sha256` is the SHA-256 of the received bytes (`original<.ext>`), the same value as the
`original_sha256` provenance field of `meta.json`. Records written before REQ-PMO-0013 (schema 1 and 2)
have no `original_sha256` inside their stored `CaseDocument`; on read it is taken from that provenance
field, which was computed from the exact received bytes at intake. Stored files are never rewritten.

Directories are created 0700 and files 0600 (P9). Single writer per data dir is assumed.
"""

import hashlib
import json
import logging
import os
import re
import shutil
import unicodedata
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePath

from legalai_casefile._cjk import CodePointSubstitution, restore_extracted_text
from legalai_casefile._common import detect_language
from legalai_casefile.errors import (
    CasefileError,
    DocumentNotFoundError,
    IntakeError,
    InvalidIdentifierError,
    InvalidRangeError,
    StoreIntegrityError,
)
from legalai_casefile.extraction import DEFAULT_MAX_BYTES, extract_document
from legalai_contracts import CaseDocument

logger = logging.getLogger(__name__)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_META_SCHEMA = 3
# 1 = before REQ-PMO-0009 (no substitution record); 2 = before REQ-PMO-0013 (no CaseDocument.original_sha256).
_READABLE_SCHEMAS = frozenset({1, 2, 3})
_LEGACY_NO_ORIGINAL_IN_DOCUMENT = frozenset({1, 2})
_CACHE_SIZE = 16


def _check_id(kind: str, value: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value) or ".." in value:
        raise InvalidIdentifierError(f"{kind} must match [A-Za-z0-9][A-Za-z0-9._-]{{0,127}} without '..'")
    return value


def derive_doc_id(case_id: str, filename: str) -> str:
    """Stable doc id for a file name within a case (name NFC-normalised, directories ignored)."""
    name = unicodedata.normalize("NFC", PurePath(filename).name)
    digest = hashlib.sha256(f"{case_id}\x00{name}".encode()).hexdigest()
    return f"cf-{digest[:20]}"


@dataclass(frozen=True)
class StoredVersion:
    """One stored version of a case document, with its provenance (P5).

    `substitutions` records every code point replaced after extraction (with `substitution_table`, the
    mapping version); `LocalCaseFileStore.get_extracted_text` rebuilds the extractor's exact output.
    """

    document: CaseDocument
    sequence: int
    original_filename: str
    original_sha256: str
    original_size: int
    extractor: str
    warnings: tuple[str, ...]
    substitutions: tuple[CodePointSubstitution, ...] = ()
    substitution_table: str | None = None


@dataclass(frozen=True)
class IntakeResult:
    """Outcome of `LocalCaseFileStore.ingest`.

    `created` is False when the file was byte-identical to the latest stored version (nothing new was
    written). `warnings` name content that is not part of the text (images, attachments, comments);
    they contain no document text and should be shown to the user.
    """

    document: CaseDocument
    created: bool
    warnings: tuple[str, ...]


def _write_private(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())


class LocalCaseFileStore:
    """Intake API and `CaseFileStore` implementation backed by `<data_dir>/casefile/`.

    The caller passes `data_dir` (it must exist); this class reads no environment variables.
    `get_text` returns exactly the stored characters for any valid range and never clamps.
    Stored text is checked against its SHA-256 on load; a mismatch raises `StoreIntegrityError`.
    """

    def __init__(self, data_dir: str | os.PathLike[str]) -> None:
        base = Path(data_dir)
        if not base.is_dir():
            raise FileNotFoundError(f"data dir does not exist: {base}")
        self._root = base / "casefile"
        self._cache: OrderedDict[tuple[str, str], str] = OrderedDict()

    # ---- intake ---------------------------------------------------------------------------------

    def ingest(
        self,
        case_id: str,
        filename: str,
        data: bytes,
        *,
        doc_id: str | None = None,
        title: str | None = None,
        language: str | None = None,
        received_at: datetime | None = None,
        encoding: str | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> IntakeResult:
        """Extract and store one file for `case_id`.

        Re-ingesting the same `doc_id` (by default derived from case and file name) with different
        bytes creates a new `version_id`; earlier versions stay readable. Identical bytes return the
        latest version unchanged. Refused files raise an `IntakeError` and nothing is stored.
        """
        _check_id("case_id", case_id)
        name = PurePath(filename).name
        if not name:
            raise InvalidIdentifierError("filename must not be empty")
        doc_id = _check_id("doc_id", doc_id) if doc_id is not None else derive_doc_id(case_id, name)
        if received_at is None:
            received_at = datetime.now(UTC)
        elif received_at.tzinfo is None:
            raise ValueError("received_at must be timezone-aware")

        doc_dir = self._root / "cases" / case_id / doc_id
        other = [p for p in self._doc_dirs(doc_id) if p != doc_dir]
        if other:
            raise InvalidIdentifierError("doc_id already belongs to another case")
        versions = self._versions_in(doc_dir) if doc_dir.is_dir() else []
        original_sha = hashlib.sha256(data).hexdigest()
        if versions and versions[-1].original_sha256 == original_sha:
            logger.info(
                "casefile intake unchanged doc_id=%s version_id=%s", doc_id, versions[-1].document.version_id
            )
            return IntakeResult(versions[-1].document, False, versions[-1].warnings)

        try:
            extraction = extract_document(name, data, encoding=encoding, max_bytes=max_bytes)
        except IntakeError as exc:
            logger.info("casefile intake refused doc_id=%s reason=%s", doc_id, exc.reason.value)
            raise
        text_bytes = extraction.text.encode("utf-8")
        sequence = len(versions) + 1
        document = CaseDocument(
            case_id=case_id,
            doc_id=doc_id,
            version_id=f"v{sequence:04d}-{original_sha[:12]}",
            title=title if title is not None else name,
            language=language if language is not None else detect_language(extraction.text),
            media_type=extraction.media_type,
            received_at=received_at,
            content_sha256=hashlib.sha256(text_bytes).hexdigest(),
            char_count=len(extraction.text),
            page_starts=extraction.page_starts,
            original_sha256=original_sha,
        )
        stored = StoredVersion(
            document=document,
            sequence=sequence,
            original_filename=name,
            original_sha256=original_sha,
            original_size=len(data),
            extractor=extraction.extractor,
            warnings=extraction.warnings,
            substitutions=extraction.substitutions,
            substitution_table=extraction.substitution_table,
        )
        self._write_version(doc_dir, stored, data, text_bytes, PurePath(name).suffix.lower())
        logger.info(
            "casefile intake stored doc_id=%s version_id=%s media_type=%s pages=%d chars=%d warnings=%d "
            "substitutions=%d",
            doc_id,
            document.version_id,
            document.media_type,
            len(document.page_starts),
            document.char_count,
            len(extraction.warnings),
            len(extraction.substitutions),
        )
        return IntakeResult(document, True, extraction.warnings)

    def ingest_file(
        self,
        case_id: str,
        path: str | os.PathLike[str],
        *,
        doc_id: str | None = None,
        title: str | None = None,
        language: str | None = None,
        received_at: datetime | None = None,
        encoding: str | None = None,
    ) -> IntakeResult:
        """`ingest` the file at `path`, using its name as the filename."""
        p = Path(path)
        return self.ingest(
            case_id,
            p.name,
            p.read_bytes(),
            doc_id=doc_id,
            title=title,
            language=language,
            received_at=received_at,
            encoding=encoding,
        )

    def _write_version(
        self, doc_dir: Path, stored: StoredVersion, original: bytes, text: bytes, ext: str
    ) -> None:
        staging = self._root / ".staging"
        for d in (self._root, staging, doc_dir.parent, doc_dir):
            d.mkdir(mode=0o700, parents=True, exist_ok=True)
        final = doc_dir / stored.document.version_id
        if final.exists():
            raise StoreIntegrityError("version directory already exists")
        tmp = staging / uuid.uuid4().hex
        tmp.mkdir(mode=0o700)
        try:
            _write_private(tmp / f"original{ext}", original)
            _write_private(tmp / "text.txt", text)
            meta = {
                "schema": _META_SCHEMA,
                "document": stored.document.model_dump(mode="json"),
                "sequence": stored.sequence,
                "original_filename": stored.original_filename,
                "original_sha256": stored.original_sha256,
                "original_size": stored.original_size,
                "extractor": stored.extractor,
                "warnings": list(stored.warnings),
                "substitutions": None
                if not stored.substitutions
                else {
                    "table": stored.substitution_table,
                    "positions": [
                        [s.offset, f"{ord(s.original):04X}", f"{ord(s.replacement):04X}"]
                        for s in stored.substitutions
                    ],
                },
            }
            _write_private(tmp / "meta.json", json.dumps(meta, ensure_ascii=False, indent=2).encode("utf-8"))
            os.rename(tmp, final)
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise

    # ---- reading --------------------------------------------------------------------------------

    def _doc_dirs(self, doc_id: str) -> list[Path]:
        cases = self._root / "cases"
        return sorted(p for p in cases.glob(f"*/{doc_id}") if p.is_dir()) if cases.is_dir() else []

    def _doc_dir(self, doc_id: str, version_id: str | None = None) -> Path:
        _check_id("doc_id", doc_id)
        found = self._doc_dirs(doc_id)
        if not found:
            raise DocumentNotFoundError(f"no document {doc_id}", doc_id=doc_id, version_id=version_id)
        if len(found) > 1:
            raise StoreIntegrityError(f"doc_id {doc_id} stored under more than one case")
        return found[0]

    @staticmethod
    def _load_meta(version_dir: Path) -> StoredVersion:
        try:
            meta = json.loads((version_dir / "meta.json").read_bytes().decode("utf-8"))
            schema = meta.get("schema")
            if schema not in _READABLE_SCHEMAS:
                raise StoreIntegrityError("unknown metadata schema")
            record = meta.get("substitutions")
            subs = (
                ()
                if record is None
                else tuple(
                    CodePointSubstitution(int(off), chr(int(orig, 16)), chr(int(repl, 16)))
                    for off, orig, repl in record["positions"]
                )
            )
            original_sha = str(meta["original_sha256"])
            document = CaseDocument.model_validate(meta["document"])
            if document.original_sha256 is None:
                if schema not in _LEGACY_NO_ORIGINAL_IN_DOCUMENT:
                    raise StoreIntegrityError(f"metadata of version {version_dir.name} lacks original_sha256")
                # Pre-REQ-PMO-0013 record: use the hash recorded at intake, validated like any contract value.
                document = CaseDocument.model_validate({**meta["document"], "original_sha256": original_sha})
            elif document.original_sha256 != original_sha:
                raise StoreIntegrityError(f"original_sha256 of version {version_dir.name} is inconsistent")
            stored = StoredVersion(
                document=document,
                sequence=int(meta["sequence"]),
                original_filename=str(meta["original_filename"]),
                original_sha256=original_sha,
                original_size=int(meta["original_size"]),
                extractor=str(meta["extractor"]),
                warnings=tuple(str(w) for w in meta["warnings"]),
                substitutions=subs,
                substitution_table=None if record is None else str(record["table"]),
            )
        except CasefileError:
            raise
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise StoreIntegrityError(f"unreadable metadata for version {version_dir.name}") from exc
        doc = stored.document
        if doc.version_id != version_dir.name or doc.doc_id != version_dir.parent.name:
            raise StoreIntegrityError("metadata does not match its location")
        if doc.case_id != version_dir.parent.parent.name:
            raise StoreIntegrityError("metadata case_id does not match its location")
        return stored

    def _versions_in(self, doc_dir: Path) -> list[StoredVersion]:
        versions = [self._load_meta(p) for p in doc_dir.iterdir() if p.is_dir()]
        versions.sort(key=lambda v: v.sequence)
        if [v.sequence for v in versions] != list(range(1, len(versions) + 1)):
            raise StoreIntegrityError("version sequence has gaps or duplicates")
        return versions

    def list_versions(self, doc_id: str) -> list[StoredVersion]:
        """All versions of a document, oldest first."""
        return self._versions_in(self._doc_dir(doc_id))

    def get_version(self, doc_id: str, version_id: str) -> StoredVersion:
        """One stored version with provenance."""
        _check_id("version_id", version_id)
        version_dir = self._doc_dir(doc_id, version_id) / version_id
        if not version_dir.is_dir():
            raise DocumentNotFoundError(
                f"no version {version_id} of {doc_id}", doc_id=doc_id, version_id=version_id
            )
        return self._load_meta(version_dir)

    def list_documents(self, case_id: str) -> list[CaseDocument]:
        """The latest version of every document in `case_id`, ordered by `doc_id`. Unknown case -> []."""
        case_dir = self._root / "cases" / _check_id("case_id", case_id)
        if not case_dir.is_dir():
            return []
        latest = []
        for doc_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            versions = self._versions_in(doc_dir)
            if versions:
                latest.append(versions[-1].document)
        return latest

    def get_document(self, doc_id: str, version_id: str) -> CaseDocument:
        """Metadata of one document version.

        Raises `DocumentNotFoundError` (a `legalai_contracts.DocumentNotFoundError`) if absent.
        """
        return self.get_version(doc_id, version_id).document

    def _text(self, doc_id: str, version_id: str) -> str:
        key = (doc_id, version_id)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        stored = self.get_version(doc_id, version_id)
        path = self._doc_dir(doc_id) / version_id / "text.txt"
        raw = path.read_bytes()
        doc = stored.document
        if hashlib.sha256(raw).hexdigest() != doc.content_sha256:
            raise StoreIntegrityError(f"stored text of {doc_id}/{version_id} does not match its hash")
        text = raw.decode("utf-8")
        if len(text) != doc.char_count:
            raise StoreIntegrityError(f"stored text of {doc_id}/{version_id} has the wrong length")
        self._cache[key] = text
        if len(self._cache) > _CACHE_SIZE:
            self._cache.popitem(last=False)
        return text

    def get_extracted_text(self, doc_id: str, version_id: str) -> str:
        """The extractor's exact output for this version, before any recorded substitution (P5).

        Equals the stored text when nothing was substituted. Raises `StoreIntegrityError` if the record
        does not match the stored text.
        """
        stored = self.get_version(doc_id, version_id)
        text = self._text(doc_id, version_id)
        try:
            return restore_extracted_text(text, stored.substitutions)
        except ValueError as exc:
            raise StoreIntegrityError(f"substitution record of {doc_id}/{version_id} does not match") from exc

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        """Exactly `text[start_char:end_char]` of the stored version (code-point offsets).

        Raises `InvalidRangeError` unless `0 <= start_char <= end_char <= char_count` (no clamping).
        """
        text = self._text(doc_id, version_id)
        for value in (start_char, end_char):
            if not isinstance(value, int) or isinstance(value, bool):
                raise InvalidRangeError("offsets must be integers")
        if not 0 <= start_char <= end_char <= len(text):
            raise InvalidRangeError(f"range [{start_char}, {end_char}) outside 0..{len(text)}")
        return text[start_char:end_char]
