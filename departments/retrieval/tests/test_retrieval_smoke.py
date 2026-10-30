import legalai_retrieval


def test_public_api_declared() -> None:
    assert isinstance(legalai_retrieval.__all__, list)
