"""LegalAI verification department. Public API: only names in __all__ may be imported by other departments.

`IndependentVerifier` implements the `legalai_contracts.Verifier` port. `interface` constructs it with a
`SourceStore`, a `CaseFileStore` and a model client (`OpenAICompatibleChatModel` built from
`VerificationModelConfig`, or any `JsonChatModel`).
"""

from legalai_verification.config import VerificationModelConfig
from legalai_verification.model_client import JsonChatModel, ModelCallError, OpenAICompatibleChatModel
from legalai_verification.verifier import VERIFIER_VERSION, IndependentVerifier

__all__: list[str] = [
    "VERIFIER_VERSION",
    "IndependentVerifier",
    "JsonChatModel",
    "ModelCallError",
    "OpenAICompatibleChatModel",
    "VerificationModelConfig",
]
