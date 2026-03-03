from fastapi import APIRouter
from datetime import timedelta, datetime
import jwt
from app.core.config import settings

router = APIRouter()

@router.post("/simple-login")
def simple_login():
    """Simple login endpoint that returns a dummy token for testing"""
    try:
        # Create a dummy JWT token for testing
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {"sub": "factory@trustseal.io", "exp": expire}
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        
        return {
            "access_token": encoded_jwt,
            "token_type": "bearer",
            "message": "Use this token for testing POST requests"
        }
    except Exception as e:
        return {"error": str(e)}

@router.post("/simple-register")
def simple_register():
    """Simple register endpoint for testing"""
    return {
        "message": "Registration successful",
        "user": {
            "email": "test@example.com",
            "name": "Test User",
            "role": "customer"
        }
    }
