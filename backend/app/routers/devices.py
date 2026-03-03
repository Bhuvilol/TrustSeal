from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
import uuid

from ..models.user import User
from ..models.device import Device
from ..models.shipment import Shipment
from ..models.enums import DeviceStatus, UserRole
from ..schemas.device import Device as DeviceSchema, DeviceCreate, DeviceUpdate
from ..database import get_db
from ..dependencies import get_current_active_user, require_roles

router = APIRouter()

@router.get("", response_model=List[DeviceSchema], include_in_schema=False)
@router.get("/", response_model=List[DeviceSchema])
def get_devices(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[DeviceStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all devices with optional filtering"""
    query = db.query(Device)
    
    if status:
        query = query.filter(Device.status == status)
    
    devices = query.offset(skip).limit(limit).all()
    return devices

@router.post("/", response_model=DeviceSchema)
def create_device(
    device: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACTORY)),
):
    """Create a new device"""
    # Check if device_uid already exists
    existing_device = db.query(Device).filter(Device.device_uid == device.device_uid).first()
    if existing_device:
        raise HTTPException(status_code=400, detail="Device UID already exists")
    
    db_device = Device(**device.dict())
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

@router.get("/{device_id}", response_model=DeviceSchema)
def get_device(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific device by ID"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device

@router.put("/{device_id}", response_model=DeviceSchema)
def update_device(
    device_id: uuid.UUID,
    device_update: DeviceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACTORY)),
):
    """Update a device"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    
    update_data = device_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(device, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Unable to update device due to data constraints")
    db.refresh(device)
    return device

@router.delete("/{device_id}")
def delete_device(
    device_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.FACTORY)),
):
    """Delete a device"""
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    assigned_shipment = (
        db.query(Shipment.id)
        .filter(Shipment.device_id == device_id)
        .first()
    )
    if assigned_shipment:
        raise HTTPException(
            status_code=409,
            detail="Device is assigned to one or more shipments. Reassign shipments before deleting the device.",
        )

    db.delete(device)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Device cannot be deleted because it is referenced by other records.",
        )
    return {"message": "Device deleted successfully"}
