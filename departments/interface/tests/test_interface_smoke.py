import legalai_interface


def test_public_api_declared() -> None:
    assert isinstance(legalai_interface.__all__, list)
