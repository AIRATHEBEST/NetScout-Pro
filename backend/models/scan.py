from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import String, Float, Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base


class ScanLog(Base):
    __tablename__ = "scan_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    network_cidr: Mapped[Optional[str]] = mapped_column(String(18))
    interface: Mapped[Optional[str]] = mapped_column(String(64))
    total_devices: Mapped[int] = mapped_column(Integer, default=0)
    new_devices: Mapped[int] = mapped_column(Integer, default=0)
    devices_left: Mapped[int] = mapped_column(Integer, default=0)
    scan_duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    stats: Mapped[Optional[Dict]] = mapped_column(JSON, default=dict)
    scan_number: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "network_cidr": self.network_cidr,
            "interface": self.interface,
            "total_devices": self.total_devices,
            "new_devices": self.new_devices,
            "devices_left": self.devices_left,
            "scan_duration_seconds": self.scan_duration_seconds,
            "stats": self.stats or {},
            "scan_number": self.scan_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(64), index=True)
    device_ip: Mapped[str] = mapped_column(String(45))
    device_mac: Mapped[Optional[str]] = mapped_column(String(17))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(String(1000))
    port: Mapped[Optional[int]] = mapped_column(Integer)
    is_acknowledged: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "device_ip": self.device_ip,
            "device_mac": self.device_mac,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "port": self.port,
            "is_acknowledged": self.is_acknowledged,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
