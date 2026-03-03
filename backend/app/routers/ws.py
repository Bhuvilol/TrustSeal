import uuid
from typing import Optional, Tuple

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..core.config import settings
from ..database import SessionLocal
from ..models.shipment import Shipment
from ..models.user import User
from ..services.realtime import shipment_connection_manager

router = APIRouter()


def _extract_bearer_token(websocket: WebSocket, token: Optional[str]) -> Optional[str]:
    if token:
        return token

    authorization = websocket.headers.get("authorization")
    if not authorization:
        return None

    parts = authorization.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _validate_jwt_token(db: Session, token: str) -> Optional[User]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None

    email = payload.get("sub")
    if not email:
        return None

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        return None
    return user


async def _authenticate_ws(
    websocket: WebSocket,
    db: Session,
    token: Optional[str],
) -> Tuple[bool, Optional[User]]:
    resolved_token = _extract_bearer_token(websocket, token)
    if not resolved_token:
        if settings.WS_REQUIRE_AUTH:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return False, None
        return True, None

    user = _validate_jwt_token(db, resolved_token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return False, None
    return True, user


@router.websocket("/shipments/{shipment_id}")
async def shipment_realtime_updates(
    websocket: WebSocket,
    shipment_id: uuid.UUID,
    token: Optional[str] = Query(default=None),
) -> None:
    db = SessionLocal()
    try:
        auth_ok, user = await _authenticate_ws(websocket, db, token)
        if not auth_ok:
            return

        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    shipment_id_str = str(shipment_id)
    await shipment_connection_manager.connect(shipment_id_str, websocket)
    await websocket.send_json(
        {
            "event": "ws.connected",
            "shipment_id": shipment_id_str,
            "authenticated": user is not None,
        }
    )

    try:
        while True:
            raw_message = await websocket.receive_text()
            if raw_message.strip().lower() == "ping":
                await websocket.send_json({"event": "ws.pong", "shipment_id": shipment_id_str})
    except WebSocketDisconnect:
        pass
    finally:
        await shipment_connection_manager.disconnect(shipment_id_str, websocket)
