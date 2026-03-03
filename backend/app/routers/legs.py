from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timezone

from ..models.user import User
from ..models.shipment import Shipment, ShipmentLeg
from ..models.enums import UserRole, LegStatus
from ..schemas.leg import ShipmentLeg as ShipmentLegSchema, ShipmentLegCreate, ShipmentLegUpdate
from ..database import get_db
import uuid
from collections.abc import Iterable
import enum as _enum
from ..dependencies import get_current_active_user, require_roles

router = APIRouter()


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}")


def _to_plain(obj):
    """Simple serializer: convert UUIDs, Enums, SQLAlchemy models and
    iterables into plain Python types suitable for JSON responses.
    """
    if obj is None:
        return None

    if isinstance(obj, uuid.UUID):
        return str(obj)

    if isinstance(obj, _enum.Enum):
        return obj.value

    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}

    if isinstance(obj, Iterable) and not isinstance(obj, (str, bytes)):
        return [_to_plain(i) for i in obj]

    if hasattr(obj, '__dict__'):
        data = {}
        for k, v in obj.__dict__.items():
            if k.startswith('_'):
                continue
            data[k] = _to_plain(v)
        return data

    return obj

@router.get("", response_model=List[ShipmentLegSchema], include_in_schema=False)
@router.get("/", response_model=List[ShipmentLegSchema])
def get_shipment_legs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    shipment_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all shipment legs with optional filtering"""
    query = db.query(ShipmentLeg)
    
    if shipment_id:
        # Verify shipment exists
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        query = query.filter(ShipmentLeg.shipment_id == shipment_id)
    
    legs = query.order_by(ShipmentLeg.leg_number).offset(skip).limit(limit).all()
    return [_to_plain(l) for l in legs]

@router.post("/", response_model=ShipmentLegSchema)
def create_shipment_leg(
    leg: ShipmentLegCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Create a new shipment leg"""
    shipment_uuid = _parse_uuid(leg.shipment_id, "shipment_id")

    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == shipment_uuid).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    
    # Check if leg number already exists for this shipment
    existing_leg = db.query(ShipmentLeg).filter(
        ShipmentLeg.shipment_id == shipment_uuid,
        ShipmentLeg.leg_number == leg.leg_number
    ).first()
    if existing_leg:
        raise HTTPException(status_code=400, detail="Leg number already exists for this shipment")
    
    payload = leg.dict()
    payload["shipment_id"] = shipment_uuid
    db_leg = ShipmentLeg(**payload)
    db.add(db_leg)
    db.commit()
    db.refresh(db_leg)
    return _to_plain(db_leg)

@router.get("/{leg_id}", response_model=ShipmentLegSchema)
def get_shipment_leg(
    leg_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific shipment leg by ID"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    return _to_plain(leg)

@router.put("/{leg_id}", response_model=ShipmentLegSchema)
def update_shipment_leg(
    leg_id: uuid.UUID,
    leg_update: ShipmentLegUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Update a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    update_data = leg_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(leg, field, value)
    
    db.commit()
    db.refresh(leg)
    return _to_plain(leg)

@router.post("/{leg_id}/start")
def start_shipment_leg(
    leg_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Start a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    leg.status = LegStatus.IN_PROGRESS
    leg.started_at = datetime.now(timezone.utc)
    
    db.commit()
    return {"message": "Shipment leg started successfully"}

@router.post("/{leg_id}/complete")
def complete_shipment_leg(
    leg_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Complete a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    leg.status = LegStatus.SETTLED
    leg.completed_at = datetime.now(timezone.utc)
    
    db.commit()
    return {"message": "Shipment leg completed successfully"}

@router.delete("/{leg_id}")
def delete_shipment_leg(
    leg_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.FACTORY)
    ),
):
    """Delete a shipment leg"""
    leg = db.query(ShipmentLeg).filter(ShipmentLeg.id == leg_id).first()
    if not leg:
        raise HTTPException(status_code=404, detail="Shipment leg not found")
    
    db.delete(leg)
    db.commit()
    return {"message": "Shipment leg deleted successfully"}
