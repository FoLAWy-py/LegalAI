"""Typed configuration for verification's model-based checks. Built and injected by `interface` (ADR-0003)."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class VerificationModelConfig(BaseModel):
    """Connection settings for the model used by Phase B checks.

    Guarantees: values are validated on construction; the API key is never shown in `repr`/`str`;
    the endpoint must use HTTPS (P9: prompts may contain excerpts of confidential case files).
    Temperature is not configurable: Phase B always uses 0 (P7).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_url: str = Field(min_length=1, description="OpenAI-compatible base URL, e.g. '.../v1/openai'.")
    api_key: SecretStr
    model: str = Field(min_length=1, description="Model id; VERIFICATION_LLM_MODEL or LLM_MODEL.")
    timeout_seconds: float = Field(default=120.0, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)
    max_output_tokens: int = Field(default=2048, gt=0)

    @field_validator("base_url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("base_url must use https://")
        return value.rstrip("/")

    @field_validator("api_key")
    @classmethod
    def _key_present(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("api_key must not be empty")
        return value
