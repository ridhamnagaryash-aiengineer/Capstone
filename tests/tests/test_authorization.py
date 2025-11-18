from src.core.security import create_access_token

def test_jwt():
    token = create_access_token({"sub": "test@example.com"})
    assert isinstance(token, str)
