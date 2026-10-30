"""Errors raised by retrieval. All derive from RetrievalError; none is ever swallowed internally."""


class RetrievalError(Exception):
    """Base class for retrieval failures."""


class IndexNotFoundError(RetrievalError):
    """No index exists for the requested jurisdiction or case. Distinct from 'no results' ([])."""


class StaleIndexError(RetrievalError):
    """The index disagrees with the store or with the configured embedder/format. Rebuild it."""


class IndexBuildError(RetrievalError):
    """The store returned data that cannot be indexed safely (wrong scope, bad text length, duplicates)."""
