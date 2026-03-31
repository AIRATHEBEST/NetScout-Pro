"""Scan history and alert endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from models.scan import ScanLog, AlertLog
from api.ws import manager

router = APIRouter(prefix="/api", tags=["scans"])


@router.get("/scans")
async def list_scans(
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List scan history."""
    q = select(ScanLog).order_by(ScanLog.created_at.desc()).limit(limit).offset(offset)
    if agent_id:
        q = q.where(ScanLog.agent_id == agent_id)
    result = await db.execute(q)
    return [s.to_dict() for s in result.scalars().all()]


@router.get("/alerts")
async def list_alerts(
    agent_id: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    unacknowledged_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """List security alerts."""
    q = select(AlertLog).order_by(AlertLog.created_at.desc()).limit(limit).offset(offset)
    if agent_id:
        q = q.where(AlertLog.agent_id == agent_id)
    if severity:
        q = q.where(AlertLog.severity == severity.upper())
    if unacknowledged_only:
        q = q.where(AlertLog.is_acknowledged == False)
    result = await db.execute(q)
    return [a.to_dict() for a in result.scalars().all()]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    """Acknowledge a security alert."""
    result = await db.execute(select(AlertLog).where(AlertLog.id == alert_id))
    alert = result.scalar_one_or_none()
    if not alert:
        return {"error": "Alert not found"}
    alert.is_acknowledged = True
    await db.commit()
    return {"ok": True, "alert_id": alert_id}


@router.get("/agents")
async def list_agents():
    """List currently connected agents."""
    return {
        "connected_agents": manager.get_connected_agents(),
        "count": len(manager.get_connected_agents()),
    }


@router.post("/agents/{agent_id}/scan")
async def trigger_scan(agent_id: str):
    """Trigger an immediate scan on a connected agent."""
    await manager.send_to_agent(agent_id, {
        "type": "command",
        "command": "scan_now",
    })
    return {"ok": True, "message": f"Scan triggered on agent {agent_id}"}


@router.post("/agents/{agent_id}/deep-scan")
async def trigger_deep_scan(agent_id: str, ip: str = Query(...)):
    """Trigger a deep nmap scan on a specific IP via agent."""
    await manager.send_to_agent(agent_id, {
        "type": "command",
        "command": "deep_scan",
        "params": {"ip": ip},
    })
    return {"ok": True, "message": f"Deep scan triggered for {ip} on agent {agent_id}"}
