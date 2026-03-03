from datetime import datetime, timedelta
from typing import Optional
import base64
import hashlib
import hmac
import secrets
from jose import JWTError, jwt
from .config import settings

try:
    import bcrypt as _bcrypt
except Exception:
    _bcrypt = None


PBKDF2_SCHEME = "pbkdf2_sha256"
PBKDF2_HASH_NAME = "sha256"
PBKDF2_ITERATIONS = 390000
SALT_SIZE_BYTES = 16


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + ("=" * (-len(data) % 4)))


def _hash_password_pbkdf2(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    salt = secrets.token_bytes(SALT_SIZE_BYTES)
    derived_key = hashlib.pbkdf2_hmac(
        PBKDF2_HASH_NAME,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return f"{PBKDF2_SCHEME}${iterations}${_b64encode(salt)}${_b64encode(derived_key)}"


def _verify_password_pbkdf2(password: str, hashed_password: str) -> bool:
    try:
        scheme, iterations_raw, salt_raw, expected_raw = hashed_password.split("$", 3)
        if scheme != PBKDF2_SCHEME:
            return False
        iterations = int(iterations_raw)
        salt = _b64decode(salt_raw)
        expected = _b64decode(expected_raw)
    except (TypeError, ValueError):
        return False

    actual = hashlib.pbkdf2_hmac(
        PBKDF2_HASH_NAME,
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def _is_bcrypt_hash(hashed_password: str) -> bool:
    return (
        hashed_password.startswith("$2a$")
        or hashed_password.startswith("$2b$")
        or hashed_password.startswith("$2y$")
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if _verify_password_pbkdf2(plain_password, hashed_password):
        return True

    # Backward compatibility for users already stored with bcrypt hashes.
    if _is_bcrypt_hash(hashed_password) and _bcrypt is not None:
        try:
            return _bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except ValueError:
            try:
                # Older bcrypt flows silently truncated to 72 bytes.
                return _bcrypt.checkpw(
                    plain_password.encode("utf-8")[:72],
                    hashed_password.encode("utf-8"),
                )
            except ValueError:
                return False

    return False


def get_password_hash(password: str) -> str:
    return _hash_password_pbkdf2(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    # Ensure exp is a numeric timestamp (UTC)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def generate_user_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_user_verification_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_verification_token(token), token_hash)
