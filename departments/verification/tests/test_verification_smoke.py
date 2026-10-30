import legalai_verification


def test_public_api_declared() -> None:
    assert isinstance(legalai_verification.__all__, list)
