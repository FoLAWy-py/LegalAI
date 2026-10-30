"""Exceptions that cross department boundaries (ADR-0007 §3)."""


class DocumentNotFoundError(LookupError):
    """A store holds no document version with the requested `doc_id` / `version_id` (ADR-0007 §3).

    Raised by `SourceStore` and `CaseFileStore` implementations from `get_document` and `get_text`. It
    means one thing only: the version is absent from that store. Every other exception from a store
    (integrity failure, I/O error, invalid range, bug) means the store could not answer, and consumers
    MUST treat it as a check error (fail closed, P3), never as "not found" and never as success.

    Consumers MUST catch this class, not a broader one such as `LookupError` or `KeyError`, so that an
    unrelated lookup bug inside a store is not mistaken for a missing document.

    Implementations MAY subclass it (for example together with their own error base). The message and
    attributes MUST NOT contain document text (P9); ids only.
    """

    def __init__(self, *args: object, doc_id: str | None = None, version_id: str | None = None) -> None:
        super().__init__(*args)
        self.doc_id = doc_id
        self.version_id = version_id
