import legalai_evaluation


def test_public_api_declared() -> None:
    assert isinstance(legalai_evaluation.__all__, list)
