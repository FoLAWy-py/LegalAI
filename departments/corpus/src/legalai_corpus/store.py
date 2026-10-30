"""File-backed `SourceStore` (legalai_contracts.ports.SourceStore) for law document versions.

Layout: `<data_dir>/corpus/store/<doc_id>/<version_id>/`
  document.json    the SourceDocument (contract model)
  text.txt         stored text, UTF-8, exactly `char_count` code points, hash = content_sha256
  units.json       structural units (pinpoints) as offsets into text.txt
  provenance.json  raw file hash/URL, extraction rule + normalization version, date evidence

Guarantees: versions are immutable once written; every read verifies the text hash (fail closed);
validity intervals of the versions of one doc_id never overlap; offsets are Python str indices
(Unicode code points), so `get_text(d, v, a, b) == full_text[a:b]` exactly.
"""

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping
from datetime import date
from pathlib import Path

from legalai_contracts import SourceDocument
from legalai_corpus.manifest import SAFE_ID
from legalai_corpus.structure import Unit

_SAFE = re.compile(SAFE_ID)


class StoreError(Exception):
    """Base class: the store cannot serve or accept a version authoritatively."""


class DocumentNotFound(StoreError, KeyError):
    pass


class IntegrityError(StoreError):
    """Stored text does not match its recorded hash or length: refuse to serve it."""


class VersionConflict(StoreError):
    """A version with this id already exists with different content (e.g. upstream changed)."""


class IntervalOverlap(StoreError):
    """Two versions of one document would both be in force on some day."""


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _overlaps(a_from: date, a_to: date | None, b_from: date, b_to: date | None) -> bool:
    """Half-open intervals [from, to); None = open-ended."""
    return (b_to is None or a_from < b_to) and (a_to is None or b_from < a_to)


class FileSourceStore:
    """Authoritative text and metadata of law document versions under `<data_dir>/corpus/store`."""

    def __init__(self, data_dir: Path) -> None:
        self.root = Path(data_dir) / "corpus" / "store"
        self._texts: dict[tuple[str, str], str] = {}

    # -- SourceStore port ---------------------------------------------------------------------------
    def list_documents(self, jurisdiction: str) -> list[SourceDocument]:
        """All stored versions in `jurisdiction` (exact code match), ordered by doc_id then effective_from."""
        docs = [d for d in self._all_documents() if d.jurisdiction == jurisdiction]
        return sorted(docs, key=lambda d: (d.doc_id, d.effective_from, d.version_id))

    def get_document(self, doc_id: str, version_id: str) -> SourceDocument:
        """The SourceDocument of one version. Raises DocumentNotFound."""
        path = self._dir(doc_id, version_id) / "document.json"
        if not path.is_file():
            raise DocumentNotFound(f"{doc_id}/{version_id}")
        return SourceDocument.model_validate_json(path.read_text(encoding="utf-8"))

    def get_text(self, doc_id: str, version_id: str, start_char: int, end_char: int) -> str:
        """Exactly the stored characters [start_char, end_char). Raises ValueError for an invalid range
        and IntegrityError if the stored text no longer matches its hash."""
        text = self.full_text(doc_id, version_id)
        if not (0 <= start_char < end_char <= len(text)):
            raise ValueError(f"range [{start_char}, {end_char}) outside 0..{len(text)}")
        return text[start_char:end_char]

    # -- corpus extensions (public, beyond the port) ------------------------------------------------
    def full_text(self, doc_id: str, version_id: str) -> str:
        """The whole stored text of a version, hash-verified."""
        key = (doc_id, version_id)
        if key not in self._texts:
            doc = self.get_document(doc_id, version_id)
            raw = (self._dir(doc_id, version_id) / "text.txt").read_bytes()
            text = raw.decode("utf-8")
            if hashlib.sha256(raw).hexdigest() != doc.content_sha256 or len(text) != doc.char_count:
                raise IntegrityError(f"{doc_id}/{version_id}: stored text does not match content_sha256")
            self._texts[key] = text
        return self._texts[key]

    def get_units(self, doc_id: str, version_id: str) -> list[Unit]:
        """Structural units (articles, paragraphs, items, headings) with offsets into the stored text."""
        self.get_document(doc_id, version_id)
        data = json.loads((self._dir(doc_id, version_id) / "units.json").read_text(encoding="utf-8"))
        return [Unit(**u) for u in data]

    def get_provenance(self, doc_id: str, version_id: str) -> dict[str, object]:
        """Raw-file provenance, extraction rule and date evidence recorded at ingestion."""
        self.get_document(doc_id, version_id)
        data: dict[str, object] = json.loads(
            (self._dir(doc_id, version_id) / "provenance.json").read_text(encoding="utf-8")
        )
        return data

    def versions(self, doc_id: str) -> list[SourceDocument]:
        return sorted(
            (d for d in self._all_documents() if d.doc_id == doc_id), key=lambda d: d.effective_from
        )

    def put(
        self,
        document: SourceDocument,
        text: str,
        units: list[Unit],
        provenance: Mapping[str, object],
    ) -> bool:
        """Store a new version. Returns False if an identical version already exists.

        Raises VersionConflict (same ids, different content), IntervalOverlap, IntegrityError (hash or
        length mismatch) or ValueError (unsafe ids, units outside the text)."""
        for ident in (document.doc_id, document.version_id):
            if not _SAFE.match(ident):
                raise ValueError(f"unsafe identifier {ident!r}")
        if text_sha256(text) != document.content_sha256 or len(text) != document.char_count:
            raise IntegrityError("text does not match content_sha256 / char_count")
        for u in units:
            if not (0 <= u.start < u.end <= len(text)):
                raise ValueError(f"unit {u.pinpoint!r} outside text")
        target = self._dir(document.doc_id, document.version_id)
        if target.exists():
            existing = self.get_document(document.doc_id, document.version_id)
            if existing.content_sha256 == document.content_sha256 and existing == document.model_copy(
                update={"retrieved_at": existing.retrieved_at}
            ):
                return False
            raise VersionConflict(
                f"{document.doc_id}/{document.version_id} exists with different content or metadata "
                f"(stored {existing.content_sha256[:12]}, new {document.content_sha256[:12]})"
            )
        for other in self.versions(document.doc_id):
            if other.jurisdiction != document.jurisdiction or other.doc_type != document.doc_type:
                raise ValueError(f"{document.doc_id}: jurisdiction/doc_type differ between versions")
            if _overlaps(
                document.effective_from, document.effective_to, other.effective_from, other.effective_to
            ):
                raise IntervalOverlap(f"{document.doc_id}: {document.version_id} overlaps {other.version_id}")
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(tempfile.mkdtemp(dir=target.parent, prefix=".tmp-"))
        try:
            (tmp / "text.txt").write_bytes(text.encode("utf-8"))
            (tmp / "units.json").write_text(
                json.dumps([u.to_json() for u in units], ensure_ascii=False, indent=0), encoding="utf-8"
            )
            (tmp / "provenance.json").write_text(
                json.dumps(provenance, ensure_ascii=False, indent=1, sort_keys=True, default=str),
                encoding="utf-8",
            )
            (tmp / "document.json").write_text(document.model_dump_json(indent=1), encoding="utf-8")
            os.replace(tmp, target)
        finally:
            if tmp.exists():
                shutil.rmtree(tmp)
        return True

    def verify_all(self) -> int:
        """Re-validate every stored version (contract model, hash, units in range). Returns the count."""
        count = 0
        for doc in self._all_documents():
            text = self.full_text(doc.doc_id, doc.version_id)
            for u in self.get_units(doc.doc_id, doc.version_id):
                if not (0 <= u.start < u.end <= len(text)):
                    raise IntegrityError(f"{doc.doc_id}/{doc.version_id}: unit {u.pinpoint} out of range")
            count += 1
        return count

    # -- internals ----------------------------------------------------------------------------------
    def _dir(self, doc_id: str, version_id: str) -> Path:
        if not (_SAFE.match(doc_id) and _SAFE.match(version_id)):
            raise DocumentNotFound(f"{doc_id}/{version_id}")
        return self.root / doc_id / version_id

    def _all_documents(self) -> list[SourceDocument]:
        if not self.root.is_dir():
            return []
        out = []
        for path in sorted(self.root.glob("*/*/document.json")):
            if path.parent.name.startswith(".") or path.parent.parent.name.startswith("."):
                continue  # in-progress temporary directory
            out.append(SourceDocument.model_validate_json(path.read_text(encoding="utf-8")))
        return out
