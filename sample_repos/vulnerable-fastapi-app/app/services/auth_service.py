from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, JWT_SECRET


passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(password: str, password_hash: str) -> bool:
    return passwords.verify(password, password_hash)


def create_access_token(username: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    return jwt.encode({"sub": username, "exp": expires_at}, JWT_SECRET, algorithm=JWT_ALGORITHM)
