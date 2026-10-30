from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Base for every cross-department model: immutable and strict about unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=False)


JURISDICTION_PATTERN = r"^[A-Z]{2}(-[A-Z0-9]{1,3})?$"
"""ISO 3166-1 alpha-2 with optional subdivision. `ZZ` is reserved for synthetic data."""

SYNTHETIC_JURISDICTION = "ZZ"
