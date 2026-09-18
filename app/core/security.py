from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_access_token(user_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()

def hash_withdrawal_code(code: str) -> str:
    """
    Hash the short-lived withdrawal code using the
    server secret so the database does not contain
    a directly brute-forceable plain SHA-256 code.
    """
    value = f"{settings.jwt_secret}:{code.strip().upper()}"
    return hashlib.sha256(value.encode()).hexdigest()


def create_withdrawal_token(
    user_id: str,
    verification_id: str,
    expires_minutes: int = 15,
) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": user_id,
        "role": "user",
        "purpose": "withdrawal_verification",
        "verification_id": verification_id,
        "iat": int(now.timestamp()),
        "exp": int(
            (
                now
                + timedelta(minutes=expires_minutes)
            ).timestamp()
        ),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
