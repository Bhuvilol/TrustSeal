from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from ..models.user import User
from ..models.custody_checkpoint import CustodyCheckpoint
from ..models.shipment import Shipment
from ..models.enums import UserRole
from ..schemas.custody import CustodyCheckpoint as CustodyCheckpointSchema, CustodyCheckpointCreate, CustodyCheckpointUpdate
from ..database import get_db
from ..dependencies import get_current_active_user, require_roles
from ..services.telemetry_stream_service import telemetry_stream_service

router = APIRouter()


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail=f"Invalid {field_name}")

@router.get("", response_model=List[CustodyCheckpointSchema], include_in_schema=False)
@router.get("/", response_model=List[CustodyCheckpointSchema])
def get_custody_checkpoints(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    shipment_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all custody checkpoints with optional filtering"""
    query = db.query(CustodyCheckpoint)
    
    if shipment_id:
        # Verify shipment exists
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        query = query.filter(CustodyCheckpoint.shipment_id == shipment_id)
    
    checkpoints = query.offset(skip).limit(limit).all()
    return checkpoints

@router.post("/", response_model=CustodyCheckpointSchema)
def create_custody_checkpoint(
    checkpoint: CustodyCheckpointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.CUSTOMER)
    ),
):
    """Create a new custody checkpoint"""
    shipment_uuid = _parse_uuid(checkpoint.shipment_id, "shipment_id")

    # Verify shipment exists
    shipment = db.query(Shipment).filter(Shipment.id == shipment_uuid).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    payload = checkpoint.dict()
    payload["shipment_id"] = shipment_uuid
    if payload.get("leg_id"):
        payload["leg_id"] = _parse_uuid(payload["leg_id"], "leg_id")

    # Set verified_by to current user if not provided.
    if payload.get("verified_by"):
        payload["verified_by"] = _parse_uuid(payload["verified_by"], "verified_by")
    else:
        payload["verified_by"] = current_user.id

    db_checkpoint = CustodyCheckpoint(**payload)
    db.add(db_checkpoint)
    db.commit()
    db.refresh(db_checkpoint)

    telemetry_stream_service.request_custody_finalization(str(shipment_uuid))
    return db_checkpoint

@router.get("/{checkpoint_id}", response_model=CustodyCheckpointSchema)
def get_custody_checkpoint(
    checkpoint_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific custody checkpoint by ID"""
    checkpoint = db.query(CustodyCheckpoint).filter(CustodyCheckpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Custody checkpoint not found")
    return checkpoint

@router.put("/{checkpoint_id}", response_model=CustodyCheckpointSchema)
def update_custody_checkpoint(
    checkpoint_id: uuid.UUID,
    checkpoint_update: CustodyCheckpointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(UserRole.ADMIN, UserRole.CUSTOMER)
    ),
):
    """Update a custody checkpoint"""
    checkpoint = db.query(CustodyCheckpoint).filter(CustodyCheckpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Custody checkpoint not found")
    
    update_data = checkpoint_update.dict(exclude_unset=True)
    if "leg_id" in update_data and update_data["leg_id"] is not None:
        update_data["leg_id"] = _parse_uuid(update_data["leg_id"], "leg_id")
    if "verified_by" in update_data and update_data["verified_by"] is not None:
        update_data["verified_by"] = _parse_uuid(update_data["verified_by"], "verified_by")
    for field, value in update_data.items():
        setattr(checkpoint, field, value)
    
    db.commit()
    db.refresh(checkpoint)
    return checkpoint

@router.delete("/{checkpoint_id}")
def delete_custody_checkpoint(
    checkpoint_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
):
    """Delete a custody checkpoint"""
    checkpoint = db.query(CustodyCheckpoint).filter(CustodyCheckpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Custody checkpoint not found")
    
    db.delete(checkpoint)
    db.commit()
    return {"message": "Custody checkpoint deleted successfully"}
