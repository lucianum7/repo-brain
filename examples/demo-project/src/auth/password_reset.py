from .token import create_reset_token

def request_reset(email: str) -> str:
    return create_reset_token(email)

