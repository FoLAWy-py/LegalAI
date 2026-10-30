import legalai_casefile


def test_public_api_declared() -> None:
    assert isinstance(legalai_casefile.__all__, list)
