from __future__ import annotations

from dataclasses import dataclass
import hmac
import json

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .core.config import settings
from .database import get_db
from .models.enums import UserRole
from .models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


@dataclass(slots=True)
class IngestAuthContext:
    channel: str
    identity: str


def _parse_token_registry(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in loaded.items():
        if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
            out[key.strip()] = value.strip()
    return out


def _validate_ingest_token(identity: str, token: str, registry: dict[str, str]) -> bool:
    expected = registry.get(identity)
    if expected is None:
        return False
    return hmac.compare_digest(expected, token)

async def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_roles(*roles: UserRole):
    async def role_dependency(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this operation",
            )
        return current_user

    return role_dependency


async def require_device_ingest_auth(
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
) -> IngestAuthContext:
    if not settings.INGEST_DEVICE_AUTH_ENABLED:
        return IngestAuthContext(channel="device", identity=x_device_id or "")

    if not x_device_id or not x_device_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device ingest credentials",
        )

    registry = _parse_token_registry(settings.INGEST_DEVICE_TOKENS_JSON)
    if not _validate_ingest_token(x_device_id, x_device_token, registry):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid device ingest credentials",
        )
    return IngestAuthContext(channel="device", identity=x_device_id)


async def require_verifier_ingest_auth(
    x_verifier_device_id: str | None = Header(default=None, alias="X-Verifier-Device-Id"),
    x_verifier_token: str | None = Header(default=None, alias="X-Verifier-Token"),
) -> IngestAuthContext:
    if not settings.INGEST_VERIFIER_AUTH_ENABLED:
        return IngestAuthContext(channel="verifier", identity=x_verifier_device_id or "")

    if not x_verifier_device_id or not x_verifier_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing verifier ingest credentials",
        )

    registry = _parse_token_registry(settings.INGEST_VERIFIER_TOKENS_JSON)
    if not _validate_ingest_token(x_verifier_device_id, x_verifier_token, registry):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verifier ingest credentials",
        )
    return IngestAuthContext(channel="verifier", identity=x_verifier_device_id)
