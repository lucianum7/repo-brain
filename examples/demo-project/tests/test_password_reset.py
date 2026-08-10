from src.auth.password_reset import request_reset

def test_request_reset():
    assert request_reset("dev@example.com")

