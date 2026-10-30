"""LegalAI corpus department. Public API: only names in __all__ may be imported by other departments.

`FileSourceStore` implements the `legalai_contracts.SourceStore` port. The ingestion API
(`ingest_manifest`, `PoliteFetcher`, ...) is for operators and the interface department's wiring.
"""

from legalai_corpus.extract import NORMALIZATION_VERSION, ExtractionError
from legalai_corpus.fetch import (
    DEFAULT_USER_AGENT,
    FetchError,
    FetchOutcome,
    PoliteFetcher,
    RawStore,
    RobotsDisallowed,
)
from legalai_corpus.ingest import IngestError, ingest_manifest, load_manifest
from legalai_corpus.manifest import Manifest
from legalai_corpus.origins import ORIGINS, Origin, OriginNotApproved, OriginStatus
from legalai_corpus.store import (
    DocumentNotFound,
    FileSourceStore,
    IntegrityError,
    IntervalOverlap,
    StoreError,
    VersionConflict,
)
from legalai_corpus.structure import Unit

__all__ = [
    "DEFAULT_USER_AGENT",
    "NORMALIZATION_VERSION",
    "ORIGINS",
    "DocumentNotFound",
    "ExtractionError",
    "FetchError",
    "FetchOutcome",
    "FileSourceStore",
    "IngestError",
    "IntegrityError",
    "IntervalOverlap",
    "Manifest",
    "Origin",
    "OriginNotApproved",
    "OriginStatus",
    "PoliteFetcher",
    "RawStore",
    "RobotsDisallowed",
    "StoreError",
    "Unit",
    "VersionConflict",
    "ingest_manifest",
    "load_manifest",
]
