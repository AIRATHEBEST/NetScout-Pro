"""Device CRUD API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.device import Device

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceUpdateRequest(BaseModel):
    custom_name: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    is_trusted: Optional[bool] = None


@router.get("")
async def list_devices(
    agent_id: Optional[str] = Query(None),
    is_online: Optional[bool] = Query(None),
    device_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List all discovered devices with optional filtering."""
    q = select(Device)

    if agent_id:
        q = q.where(Device.agent_id == agent_id)
    if is_online is not None:
        q = q.where(Device.is_online == is_online)
    if device_type:
        q = q.where(Device.device_type == device_type)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            Device.ip.ilike(pattern)
            | Device.hostname.ilike(pattern)
            | Device.mac.ilike(pattern)
            | Device.vendor.ilike(pattern)
            | Device.custom_name.ilike(pattern)
        )

    q = q.order_by(Device.last_seen.desc()).limit(limit).offset(offset)

    result = await db.execute(q)
    devices = result.scalars().all()
    return [d.to_dict() for d in devices]


@router.get("/{device_id}")
async def get_device(device_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single device by ID."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return device.to_dict()


@router.patch("/{device_id}")
async def update_device(
    device_id: int,
    body: DeviceUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update device metadata (name, tags, notes, trust status)."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if body.custom_name is not None:
        device.custom_name = body.custom_name
    if body.tags is not None:
        device.tags = body.tags
    if body.notes is not None:
        device.notes = body.notes
    if body.is_trusted is not None:
        device.is_trusted = body.is_trusted

    await db.commit()
    return device.to_dict()


@router.get("/{device_id}/ports")
async def get_device_ports(device_id: int, db: AsyncSession = Depends(get_db)):
    """Get all open ports for a device."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"device_id": device_id, "ip": device.ip, "ports": device.ports or []}


@router.get("/{device_id}/vulnerabilities")
async def get_device_vulnerabilities(device_id: int, db: AsyncSession = Depends(get_db)):
    """Get vulnerability findings for a device."""
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    return {
        "device_id": device_id,
        "ip": device.ip,
        "vulnerabilities": device.vulnerabilities or [],
    }


@router.get("/stats/summary")
async def get_stats(
    agent_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get network summary stats."""
    from sqlalchemy import func

    q = select(
        func.count(Device.id).label("total"),
        func.count(Device.id).filter(Device.is_online == True).label("online"),
        func.count(Device.id).filter(Device.is_trusted == True).label("trusted"),
    )
    if agent_id:
        q = q.where(Device.agent_id == agent_id)

    result = await db.execute(q)
    row = result.one()

    # Count by device type
    type_q = select(Device.device_type, func.count(Device.id)).group_by(Device.device_type)
    if agent_id:
        type_q = type_q.where(Device.agent_id == agent_id)
    type_result = await db.execute(type_q)
    by_type = {row[0] or "unknown": row[1] for row in type_result.all()}

    # Count devices with vulnerabilities
    vuln_q = select(func.count(Device.id)).where(Device.vulnerabilities != "[]")
    if agent_id:
        vuln_q = vuln_q.where(Device.agent_id == agent_id)
    vuln_result = await db.execute(vuln_q)
    vuln_count = vuln_result.scalar()

    return {
        "total_devices": row.total,
        "online_devices": row.online,
        "trusted_devices": row.trusted,
        "devices_with_vulnerabilities": vuln_count,
        "by_type": by_type,
    }
