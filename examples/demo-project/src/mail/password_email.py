def send_password_email(email: str, token: str) -> str:
    return f"to={email} token={token}"

