from app.services.auth_service import create_access_token


def test_create_access_token_returns_text() -> None:
    assert isinstance(create_access_token("alice"), str)
