import legalai_reasoning


def test_public_api_declared() -> None:
    assert isinstance(legalai_reasoning.__all__, list)
