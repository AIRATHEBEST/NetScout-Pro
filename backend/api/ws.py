"""
WebSocket hub.
- Agent connections: send scan data IN
- Dashboard connections: receive live updates OUT
"""

import json
import logging
import time
from typing import Dict, Set

from fastapi import WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # Agent connections: agent_id -> WebSocket
        self.agents: Dict[str, WebSocket] = {}
        # Dashboard connections: set of WebSockets
        self.dashboards: Set[WebSocket] = set()

    async def connect_agent(self, agent_id: str, ws: WebSocket):
        await ws.accept()
        self.agents[agent_id] = ws
        logger.info(f"Agent {agent_id} connected (total agents: {len(self.agents)})")

    def disconnect_agent(self, agent_id: str):
        self.agents.pop(agent_id, None)
        logger.info(f"Agent {agent_id} disconnected")

    async def connect_dashboard(self, ws: WebSocket):
        await ws.accept()
        self.dashboards.add(ws)
        logger.info(f"Dashboard connected (total: {len(self.dashboards)})")

    def disconnect_dashboard(self, ws: WebSocket):
        self.dashboards.discard(ws)
        logger.info(f"Dashboard disconnected")

    async def broadcast_to_dashboards(self, message: dict):
        """Send a message to all connected dashboard clients."""
        dead = set()
        for ws in self.dashboards:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.dashboards.discard(ws)

    async def send_to_agent(self, agent_id: str, message: dict):
        """Send a command to a specific agent."""
        ws = self.agents.get(agent_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send to agent {agent_id}: {e}")
                self.disconnect_agent(agent_id)
        else:
            logger.warning(f"Agent {agent_id} not connected")

    def get_connected_agents(self):
        return list(self.agents.keys())


manager = ConnectionManager()


async def agent_websocket_handler(
    websocket: WebSocket,
    db: AsyncSession,
):
    """Handle WebSocket connection from a local agent."""
    agent_id = None

    try:
        await websocket.accept()

        # First message must be auth
        raw = await websocket.receive_text()
        auth_msg = json.loads(raw)

        if auth_msg.get("type") != "auth":
            await websocket.send_json({"type": "auth_error", "error": "First message must be auth"})
            await websocket.close()
            return

        if auth_msg.get("token") != settings.AGENT_TOKEN:
            await websocket.send_json({"type": "auth_error", "error": "Invalid token"})
            await websocket.close()
            return

        agent_id = auth_msg.get("agent_id", "unknown")

        # Register agent (replace existing accept with our manager)
        manager.agents[agent_id] = websocket
        logger.info(f"Agent {agent_id} authenticated")

        await websocket.send_json({"type": "auth_ok", "agent_id": agent_id})

        # Main message loop
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")

            if msg_type == "scan_result":
                await _handle_scan_result(message, db)

            elif msg_type in ("device_joined", "device_left", "device_updated"):
                await _handle_device_event(msg_type, message, db)

            elif msg_type == "alert":
                await _handle_alert(message, db)

            elif msg_type == "heartbeat":
                logger.debug(f"Heartbeat from {agent_id}")
                # Forward agent status to dashboards
                await manager.broadcast_to_dashboards({
                    "type": "agent_status",
                    "agent_id": agent_id,
                    "status": "online",
                    "timestamp": time.time(),
                })

            elif msg_type == "pong":
                pass

    except WebSocketDisconnect:
        logger.info(f"Agent {agent_id} disconnected cleanly")
    except Exception as e:
        logger.error(f"Agent WS error ({agent_id}): {e}")
    finally:
        if agent_id:
            manager.disconnect_agent(agent_id)
            await manager.broadcast_to_dashboards({
                "type": "agent_status",
                "agent_id": agent_id,
                "status": "offline",
                "timestamp": time.time(),
            })


async def dashboard_websocket_handler(websocket: WebSocket):
    """Handle WebSocket connection from a dashboard client."""
    await manager.connect_dashboard(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "connected_agents": manager.get_connected_agents(),
            "timestamp": time.time(),
        })

        # Keep connection alive, listen for client commands
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
                cmd = message.get("type")

                if cmd == "trigger_scan":
                    agent_id = message.get("agent_id")
                    if agent_id:
                        await manager.send_to_agent(agent_id, {
                            "type": "command",
                            "command": "scan_now",
                        })

                elif cmd == "deep_scan":
                    agent_id = message.get("agent_id")
                    ip = message.get("ip")
                    if agent_id and ip:
                        await manager.send_to_agent(agent_id, {
                            "type": "command",
                            "command": "deep_scan",
                            "params": {"ip": ip},
                        })

            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Dashboard WS error: {e}")
    finally:
        manager.disconnect_dashboard(websocket)


async def _handle_scan_result(message: dict, db: AsyncSession):
    """Process and store a full scan result from an agent."""
    from models.scan import ScanLog
    from models.device import Device
    from sqlalchemy import select
    from datetime import datetime

    data = message.get("data", {})
    agent_id = message.get("agent_id", "unknown")
    network = data.get("network", {})
    devices = data.get("devices", [])
    stats = data.get("stats", {})

    # Save scan log
    scan_log = ScanLog(
        agent_id=agent_id,
        network_cidr=network.get("network_cidr"),
        interface=network.get("interface"),
        total_devices=stats.get("total_devices", len(devices)),
        new_devices=stats.get("new_devices", 0),
        devices_left=stats.get("devices_left", 0),
        scan_duration_seconds=stats.get("scan_duration_seconds"),
        stats=stats,
        scan_number=data.get("scan_number", 0),
    )
    db.add(scan_log)

    # Upsert devices
    for device_data in devices:
        ip = device_data.get("ip")
        if not ip:
            continue

        result = await db.execute(
            select(Device).where(
                Device.ip == ip,
                Device.agent_id == agent_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.mac = device_data.get("mac", existing.mac)
            existing.hostname = device_data.get("hostname") or existing.hostname
            existing.vendor = device_data.get("vendor") or existing.vendor
            existing.device_type = device_data.get("device_type", existing.device_type)
            existing.os_info = device_data.get("os_info", existing.os_info)
            existing.ports = device_data.get("ports", existing.ports)
            existing.vulnerabilities = device_data.get("vulnerabilities", [])
            existing.mdns_name = device_data.get("mdns_name", existing.mdns_name)
            existing.mdns_services = device_data.get("mdns_services", existing.mdns_services)
            existing.is_online = device_data.get("is_online", True)
            existing.last_seen = datetime.utcnow()
            existing.network_cidr = network.get("network_cidr")
        else:
            new_device = Device(
                ip=ip,
                mac=device_data.get("mac", ""),
                hostname=device_data.get("hostname", ""),
                vendor=device_data.get("vendor", ""),
                device_type=device_data.get("device_type", "unknown"),
                os_info=device_data.get("os_info", {}),
                ports=device_data.get("ports", []),
                vulnerabilities=device_data.get("vulnerabilities", []),
                mdns_name=device_data.get("mdns_name"),
                mdns_services=device_data.get("mdns_services", []),
                discovery_method=device_data.get("discovery_method", "ARP"),
                is_online=True,
                agent_id=agent_id,
                network_cidr=network.get("network_cidr"),
            )
            db.add(new_device)

    await db.commit()

    # Broadcast to all dashboards
    await manager.broadcast_to_dashboards({
        "type": "scan_result",
        "agent_id": agent_id,
        "data": data,
        "timestamp": time.time(),
    })


async def _handle_device_event(event_type: str, message: dict, db: AsyncSession):
    """Handle device joined/left/updated events."""
    from models.device import Device
    from sqlalchemy import select
    from datetime import datetime

    agent_id = message.get("agent_id", "unknown")
    device_data = message.get("device", {})
    ip = device_data.get("ip")

    if not ip:
        return

    if event_type == "device_left":
        result = await db.execute(
            select(Device).where(Device.ip == ip, Device.agent_id == agent_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.is_online = False
            existing.last_seen = datetime.utcnow()
            await db.commit()
    else:
        # device_joined or device_updated — handled in scan_result upsert
        pass

    # Broadcast to dashboards
    await manager.broadcast_to_dashboards({
        "type": event_type,
        "agent_id": agent_id,
        "device": device_data,
        "timestamp": time.time(),
    })


async def _handle_alert(message: dict, db: AsyncSession):
    """Store and broadcast security alerts."""
    from models.scan import AlertLog

    agent_id = message.get("agent_id", "unknown")
    alert = message.get("alert", {})
    vuln = alert.get("vulnerability", {})

    alert_log = AlertLog(
        agent_id=agent_id,
        device_ip=alert.get("device_ip", ""),
        device_mac=alert.get("device_mac", ""),
        severity=vuln.get("severity", "LOW"),
        title=vuln.get("title", ""),
        description=vuln.get("description", ""),
        port=vuln.get("port"),
    )
    db.add(alert_log)
    await db.commit()

    await manager.broadcast_to_dashboards({
        "type": "alert",
        "agent_id": agent_id,
        "alert": {
            **alert,
            "id": alert_log.id,
        },
        "timestamp": time.time(),
    })
