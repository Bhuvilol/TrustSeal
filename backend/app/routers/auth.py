from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from datetime import datetime, timezone

from ..core import security
from ..core.config import settings
from ..models.user import User
from ..schemas.token import Token, RegisterResponse, VerifyTokenRequest, VerifyTokenResponse
from ..schemas.user import User as UserSchema, UserCreate
from ..database import get_db
from ..dependencies import get_current_user

router = APIRouter()

@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    hashed_password = security.get_password_hash(user.password)
    verification_token = security.generate_user_verification_token()
    verification_token_hash = security.hash_verification_token(verification_token)
    verification_token_expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.VERIFICATION_TOKEN_EXPIRE_MINUTES
    )

    db_user = User(
        email=user.email,
        name=user.name,
        password_hash=hashed_password,
        role=user.role,
        verification_token_hash=verification_token_hash,
        verification_token_expires_at=verification_token_expires_at,
        is_verified=False,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": db_user.email, "role": db_user.role.value},
        expires_delta=access_token_expires,
    )

    return {
        "user": db_user,
        "access_token": access_token,
        "token_type": "bearer",
        "verification_token": verification_token,
        "verification_token_expires_at": verification_token_expires_at,
    }

@router.post("/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """Authenticate user and return access token"""
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email, "role": user.role.value, "user_id": str(user.id)},
        expires_delta=access_token_expires,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role.value,
        "user_id": str(user.id),
    }

@router.post("/verify", response_model=VerifyTokenResponse)
def verify_user_registration_token(
    request: VerifyTokenRequest,
    db: Session = Depends(get_db),
):
    """Verify a user registration token generated at signup time."""
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

    if user.is_verified:
        return {"message": "User already verified", "verified": True}

    if not user.verification_token_hash or not user.verification_token_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification token for user",
        )

    expires_at = user.verification_token_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        user.verification_token_hash = None
        user.verification_token_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token expired",
        )

    is_valid_token = security.verify_user_verification_token(
        request.verification_token,
        user.verification_token_hash,
    )
    if not is_valid_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

    user.is_verified = True
    user.verification_token_hash = None
    user.verification_token_expires_at = None
    db.commit()

    return {"message": "User verified successfully", "verified": True}

@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user
