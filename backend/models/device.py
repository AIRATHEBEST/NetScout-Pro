from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import String, Float, Boolean, Integer, JSON, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column
from db.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    mac: Mapped[str] = mapped_column(String(17), nullable=False, index=True)
    hostname: Mapped[Optional[str]] = mapped_column(String(255))
    vendor: Mapped[Optional[str]] = mapped_column(String(255))
    device_type: Mapped[Optional[str]] = mapped_column(String(64))
    os_info: Mapped[Optional[Dict]] = mapped_column(JSON, default=dict)
    ports: Mapped[Optional[List]] = mapped_column(JSON, default=list)
    vulnerabilities: Mapped[Optional[List]] = mapped_column(JSON, default=list)
    mdns_name: Mapped[Optional[str]] = mapped_column(String(255))
    mdns_services: Mapped[Optional[List]] = mapped_column(JSON, default=list)
    discovery_method: Mapped[Optional[str]] = mapped_column(String(32))
    is_online: Mapped[bool] = mapped_column(Boolean, default=True)
    is_trusted: Mapped[bool] = mapped_column(Boolean, default=False)
    custom_name: Mapped[Optional[str]] = mapped_column(String(255))
    tags: Mapped[Optional[List]] = mapped_column(JSON, default=list)
    notes: Mapped[Optional[str]] = mapped_column(String(1000))
    agent_id: Mapped[Optional[str]] = mapped_column(String(64))
    network_cidr: Mapped[Optional[str]] = mapped_column(String(18))
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_devices_ip_agent", "ip", "agent_id"),
        Index("ix_devices_mac_agent", "mac", "agent_id"),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ip": self.ip,
            "mac": self.mac,
            "hostname": self.hostname,
            "vendor": self.vendor,
            "device_type": self.device_type,
            "os_info": self.os_info or {},
            "ports": self.ports or [],
            "vulnerabilities": self.vulnerabilities or [],
            "mdns_name": self.mdns_name,
            "mdns_services": self.mdns_services or [],
            "discovery_method": self.discovery_method,
            "is_online": self.is_online,
            "is_trusted": self.is_trusted,
            "custom_name": self.custom_name,
            "tags": self.tags or [],
            "notes": self.notes,
            "agent_id": self.agent_id,
            "network_cidr": self.network_cidr,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }
