from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def hash_api_key(api_key: str) -> str:
    return pwd_context.hash(api_key)


def verify_api_key(api_key: str, hashed: str) -> bool:
    return pwd_context.verify(api_key, hashed)


def create_access_token(subject: str | UUID, extra: dict | None = None) -> str:
    to_encode = {"sub": str(subject)}
    if extra:
        to_encode.update(extra)
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])


def get_token_subject(token: str) -> str | None:
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except JWTError:
        return None
