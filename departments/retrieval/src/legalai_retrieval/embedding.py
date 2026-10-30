"""Dense embedders. All run locally (ADR-0003): no embedding call ever leaves the machine."""

import hashlib
import importlib
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from legalai_retrieval.text import tokenize

Matrix = npt.NDArray[np.float32]


@runtime_checkable
class Embedder(Protocol):
    """Maps text to L2-normalised vectors. Cosine similarity = dot product.

    `min_similarity` is the eligibility threshold calibrated for this model: a chunk whose
    similarity to the query is below it is not returned on semantic grounds.
    """

    @property
    def model_id(self) -> str: ...

    @property
    def min_similarity(self) -> float: ...

    def embed_documents(self, texts: Sequence[str]) -> Matrix: ...

    def embed_queries(self, texts: Sequence[str]) -> Matrix: ...


def _normalize_rows(m: Matrix) -> Matrix:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out: Matrix = (m / norms).astype(np.float32)
    return out


class HashingEmbedder:
    """Deterministic, model-free fake: hashed bag of lexical tokens. NOT semantic.

    For tests and offline runs only. It has no cross-lingual ability; any cross-lingual result
    obtained with it comes from the lexical glossary path.
    """

    def __init__(self, dimension: int = 1024, min_similarity: float = 0.5) -> None:
        if dimension < 8:
            raise ValueError("dimension must be >= 8")
        self._dim = dimension
        self._min = min_similarity

    @property
    def model_id(self) -> str:
        return f"hashing-fake-{self._dim}"

    @property
    def min_similarity(self) -> float:
        return self._min

    def _embed(self, texts: Sequence[str]) -> Matrix:
        out = np.zeros((len(texts), self._dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for token, count in Counter(tokenize(text)).items():
                digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
                h = int.from_bytes(digest, "big")
                sign = 1.0 if h & 1 else -1.0
                out[row, (h >> 1) % self._dim] += sign * (1.0 + math.log(count))
        return _normalize_rows(out)

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        return self._embed(texts)

    def embed_queries(self, texts: Sequence[str]) -> Matrix:
        return self._embed(texts)


@dataclass(frozen=True)
class EmbeddingModelSpec:
    """How to run one open-weight model, and its calibrated eligibility threshold."""

    name: str
    license: str
    min_similarity: float
    query_prefix: str = ""
    document_prefix: str = ""
    query_prompt_name: str | None = None
    recommended: bool = True
    note: str = ""


_E5_NOTE = "cross-lingual zh<->en recall@5 <= 0.36 and negatives overlap positives; not recommended"

KNOWN_MODELS: dict[str, EmbeddingModelSpec] = {
    spec.name: spec
    for spec in (
        EmbeddingModelSpec(
            "Qwen/Qwen3-Embedding-0.6B",
            "Apache-2.0",
            0.45,
            query_prompt_name="query",
            note="default: best zh<->en recall and widest positive/negative similarity gap",
        ),
        EmbeddingModelSpec(
            "BAAI/bge-m3", "MIT", 0.50, note="strong; weights only as pickled pytorch_model.bin"
        ),
        EmbeddingModelSpec(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "Apache-2.0",
            0.50,
            note="small; positive and negative similarities overlap",
        ),
        EmbeddingModelSpec(
            "intfloat/multilingual-e5-base",
            "MIT",
            0.85,
            query_prefix="query: ",
            document_prefix="passage: ",
            recommended=False,
            note=_E5_NOTE,
        ),
        EmbeddingModelSpec(
            "intfloat/multilingual-e5-small",
            "MIT",
            0.85,
            query_prefix="query: ",
            document_prefix="passage: ",
            recommended=False,
            note=_E5_NOTE,
        ),
    )
}
"""Thresholds are calibrated on retrieval's synthetic ZZ set (REQ-PMO-0003 §8): each lies between the
highest similarity of any negative query and the lowest similarity of an expected span. They MUST be
re-calibrated on the evaluation golden set (REQ-PMO-0005) before release."""

DEFAULT_EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"
"""The model interface should wire by default; chosen by the comparison in REQ-PMO-0003 §8."""


class SentenceTransformerEmbedder:
    """Local sentence-transformers model, loaded from local files only (never downloads).

    Requires the optional `embeddings` extra. Weights must already be on disk, either at
    `model_path` or in the local Hugging Face cache under `spec.name`.
    """

    def __init__(
        self,
        spec: EmbeddingModelSpec,
        model_path: Path | None = None,
        *,
        device: str | None = None,
        batch_size: int = 16,
        max_seq_length: int | None = 512,
    ) -> None:
        module = importlib.import_module("sentence_transformers")
        self._spec = spec
        self._batch_size = batch_size
        self._model = module.SentenceTransformer(
            str(model_path) if model_path else spec.name,
            device=device,
            local_files_only=True,
            trust_remote_code=False,
        )
        if max_seq_length is not None:
            self._model.max_seq_length = max_seq_length

    @classmethod
    def from_name(
        cls,
        name: str,
        model_path: Path | None = None,
        *,
        device: str | None = None,
        batch_size: int = 16,
        max_seq_length: int | None = 512,
    ) -> "SentenceTransformerEmbedder":
        """Embedder for a model in KNOWN_MODELS (which carries its calibrated threshold)."""
        if name not in KNOWN_MODELS:
            raise ValueError(f"no calibrated spec for {name!r}; known: {sorted(KNOWN_MODELS)}")
        return cls(
            KNOWN_MODELS[name],
            model_path,
            device=device,
            batch_size=batch_size,
            max_seq_length=max_seq_length,
        )

    @property
    def model_id(self) -> str:
        return self._spec.name

    @property
    def min_similarity(self) -> float:
        return self._spec.min_similarity

    def _encode(self, texts: Sequence[str], prefix: str, prompt_name: str | None) -> Matrix:
        inputs = [prefix + t for t in texts]
        kwargs: dict[str, object] = {
            "batch_size": self._batch_size,
            "normalize_embeddings": True,
            "convert_to_numpy": True,
            "show_progress_bar": False,
        }
        if prompt_name:
            kwargs["prompt_name"] = prompt_name
        vectors = np.asarray(self._model.encode(inputs, **kwargs), dtype=np.float32)
        return _normalize_rows(vectors.reshape(len(texts), -1))

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        return self._encode(texts, self._spec.document_prefix, None)

    def embed_queries(self, texts: Sequence[str]) -> Matrix:
        return self._encode(texts, self._spec.query_prefix, self._spec.query_prompt_name)
