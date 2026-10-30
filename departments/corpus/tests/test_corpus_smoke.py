import legalai_corpus


def test_public_api_declared() -> None:
    assert isinstance(legalai_corpus.__all__, list)
