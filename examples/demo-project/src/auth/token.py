EXPIRATION_SECONDS = 3600

def create_reset_token(email: str) -> str:
    return f"reset:{email}"

