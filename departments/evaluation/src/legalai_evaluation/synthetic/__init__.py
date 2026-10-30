"""The synthetic `ZZ` criminal outline set (REQ-PMO-0005 §2.1), built deterministically in memory."""

from dataclasses import dataclass

from legalai_evaluation.dataset import EvalDataset
from legalai_evaluation.fakes import (
    InMemoryCaseFileStore,
    InMemoryEvidenceRetriever,
    InMemoryRetriever,
    InMemorySourceStore,
)
from legalai_evaluation.synthetic._adversarial import build_adversarial_set
from legalai_evaluation.synthetic._cases import DATASET_VERSION, build_cases
from legalai_evaluation.synthetic._law import build_law_library

SYNTHETIC_DATASET_ID = "ZZ-SYNTH-CRIM-OUTLINE"


@dataclass(frozen=True)
class SyntheticDataset(EvalDataset):
    """The synthetic set plus in-memory retrieval fakes over exactly the spans the expected outlines cite.

    `source_store` and `case_file_store` are `InMemorySourceStore` / `InMemoryCaseFileStore`; `retriever`
    and `evidence_retriever` index article-level law spans and line-level case-file passages.
    """

    retriever: InMemoryRetriever
    evidence_retriever: InMemoryEvidenceRetriever


def load_synthetic_dataset() -> SyntheticDataset:
    """Build the synthetic `ZZ` dataset. Deterministic: two calls yield equal fingerprints."""
    law = build_law_library()
    built = build_cases(law)
    files = [f for b in built for f in b.files]
    cases = tuple(b.case for b in built)
    source_store = InMemorySourceStore((d.document, d.text) for d in law.docs)
    case_store = InMemoryCaseFileStore((f.document, f.text) for f in files)
    manifest = tuple(
        [f"law:{d.key}:{d.document.content_sha256}" for d in law.docs]
        + [
            f"case_file:{f.document.doc_id}@{f.document.version_id}:{f.document.content_sha256}"
            for f in files
        ]
    )
    return SyntheticDataset(
        dataset_id=SYNTHETIC_DATASET_ID,
        version=DATASET_VERSION,
        cases=cases,
        adversarial=tuple(build_adversarial_set(cases, law, files)),
        source_store=source_store,
        case_file_store=case_store,
        document_manifest=manifest,
        retriever=InMemoryRetriever(source_store, [s for d in law.docs for s in d.indexed()]),
        evidence_retriever=InMemoryEvidenceRetriever(case_store, [s for f in files for s in f.indexed()]),
    )
