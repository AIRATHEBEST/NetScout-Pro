"""
NetScout Local Network Agent
Main entry point — orchestrates discovery, scanning, and reporting.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, List, Optional

import colorlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    SCAN_INTERVAL_SECONDS,
    ENABLE_PORT_SCAN,
    ENABLE_MDNS,
    AGENT_ID,
)
from scanner.arp_scanner import discover_network
from scanner.nmap_scanner import quick_scan, scan_device, check_vulnerability_indicators
from scanner.mdns_scanner import scan_mdns, enrich_device_with_mdns
from scanner.mac_vendor import lookup_vendor, lookup_vendor_offline
from transport.ws_client import AgentWebSocketClient


# ---- Logging Setup ----

def setup_logging():
    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold_red",
        },
    ))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logging.getLogger("scapy").setLevel(logging.WARNING)
    logging.getLogger("zeroconf").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


# ---- Agent State ----

class AgentState:
    def __init__(self):
        self.known_devices: Dict[str, Dict] = {}  # ip -> device
        self.last_scan_time: Optional[float] = None
        self.scan_count: int = 0


# ---- Core Scanning Logic ----

async def run_full_scan(state: AgentState, ws_client: AgentWebSocketClient):
    """
    Full network scan cycle:
    1. ARP + ICMP discovery
    2. mDNS enrichment
    3. MAC vendor lookup
    4. Port scanning (quick)
    5. Deep nmap + vuln check for new/changed devices
    6. Diff against known devices → events
    7. Push to backend
    """
    logger.info(f"=== Scan #{state.scan_count + 1} starting ===")
    scan_start = time.time()

    # --- Step 1: Network discovery ---
    try:
        discovery = await asyncio.get_event_loop().run_in_executor(
            None, discover_network
        )
    except Exception as e:
        logger.error(f"Discovery failed: {e}")
        return

    devices = discovery["devices"]
    network_info = {
        "interface": discovery["interface"],
        "network_cidr": discovery["network_cidr"],
        "local_ip": discovery["local_ip"],
    }
    logger.info(f"Discovered {len(devices)} devices on {discovery['network_cidr']}")

    # --- Step 2: mDNS enrichment ---
    mdns_devices = []
    if ENABLE_MDNS:
        try:
            mdns_devices = await asyncio.get_event_loop().run_in_executor(
                None, scan_mdns
            )
            devices = [enrich_device_with_mdns(d, mdns_devices) for d in devices]
        except Exception as e:
            logger.warning(f"mDNS scan failed: {e}")

    # --- Step 3: MAC vendor lookup ---
    for device in devices:
        mac = device.get("mac", "")
        # Try offline first (fast), then online
        vendor = lookup_vendor_offline(mac)
        if not vendor:
            try:
                vendor = await asyncio.get_event_loop().run_in_executor(
                    None, lookup_vendor, mac
                )
            except Exception:
                vendor = ""
        device["vendor"] = vendor

    # --- Step 4: Port scanning ---
    if ENABLE_PORT_SCAN:
        port_scan_tasks = []
        for device in devices:
            ip = device["ip"]
            task = asyncio.get_event_loop().run_in_executor(
                None, quick_scan, ip
            )
            port_scan_tasks.append((device, task))

        for device, task in port_scan_tasks:
            try:
                scan_result = await task
                device["ports"] = scan_result.get("ports", [])
                if not device.get("os_info"):
                    device["os_info"] = scan_result.get("os_info", {})
                if device.get("device_type", "unknown") == "unknown":
                    device["device_type"] = scan_result.get("device_type", "unknown")
            except Exception as e:
                logger.error(f"Port scan error for {device['ip']}: {e}")
                device["ports"] = []

    # --- Step 5: Vulnerability indicators ---
    for device in devices:
        try:
            vulns = check_vulnerability_indicators(
                device["ip"], device.get("ports", [])
            )
            device["vulnerabilities"] = vulns
            if vulns:
                for vuln in vulns:
                    if vuln["severity"] in ("HIGH", "CRITICAL"):
                        await ws_client.send_alert({
                            "device_ip": device["ip"],
                            "device_mac": device.get("mac", ""),
                            "vulnerability": vuln,
                        })
        except Exception as e:
            logger.error(f"Vuln check error for {device['ip']}: {e}")

    # --- Step 6: Diff against known devices ---
    current_ips = {d["ip"] for d in devices}
    known_ips = set(state.known_devices.keys())

    new_ips = current_ips - known_ips
    left_ips = known_ips - current_ips
    seen_ips = current_ips & known_ips

    # New devices
    for device in devices:
        if device["ip"] in new_ips:
            logger.info(f"NEW device: {device['ip']} ({device.get('hostname', 'unknown')}) [{device.get('vendor', '')}]")
            await ws_client.send_device_event("device_joined", device)

    # Devices that left
    for ip in left_ips:
        old_device = state.known_devices[ip]
        logger.info(f"GONE device: {ip} ({old_device.get('hostname', 'unknown')})")
        await ws_client.send_device_event("device_left", {
            **old_device,
            "is_online": False,
            "last_seen": old_device.get("last_seen"),
        })

    # Updated devices (check for meaningful changes)
    for device in devices:
        if device["ip"] in seen_ips:
            old = state.known_devices[device["ip"]]
            if _device_changed(old, device):
                logger.info(f"UPDATED device: {device['ip']}")
                await ws_client.send_device_event("device_updated", device)

    # --- Step 7: Push full scan result ---
    scan_duration = time.time() - scan_start
    await ws_client.send_scan_result({
        "network": network_info,
        "devices": devices,
        "stats": {
            "total_devices": len(devices),
            "new_devices": len(new_ips),
            "devices_left": len(left_ips),
            "scan_duration_seconds": round(scan_duration, 2),
            "mdns_devices_found": len(mdns_devices),
        },
        "scan_number": state.scan_count + 1,
    })

    # --- Update state ---
    state.known_devices = {d["ip"]: d for d in devices}
    state.last_scan_time = time.time()
    state.scan_count += 1

    logger.info(
        f"=== Scan #{state.scan_count} complete in {scan_duration:.1f}s "
        f"| {len(devices)} devices | {len(new_ips)} new | {len(left_ips)} left ==="
    )


def _device_changed(old: Dict, new: Dict) -> bool:
    """Detect meaningful changes in a device record."""
    # Check if open ports changed
    old_ports = {p["port"] for p in old.get("ports", [])}
    new_ports = {p["port"] for p in new.get("ports", [])}
    if old_ports != new_ports:
        return True

    # Check if hostname changed
    if old.get("hostname") != new.get("hostname"):
        return True

    # Check if OS changed
    if old.get("os_info", {}).get("name") != new.get("os_info", {}).get("name"):
        return True

    return False


async def handle_backend_command(message: Dict, state: AgentState, ws_client: AgentWebSocketClient):
    """Handle on-demand commands from the backend."""
    command = message.get("command")
    params = message.get("params", {})

    if command == "scan_now":
        logger.info("Received scan_now command from backend")
        await run_full_scan(state, ws_client)

    elif command == "deep_scan":
        ip = params.get("ip")
        if not ip:
            logger.warning("deep_scan command missing ip param")
            return
        logger.info(f"Deep scanning {ip} on demand")
        result = await asyncio.get_event_loop().run_in_executor(
            None, scan_device, ip
        )
        await ws_client.send_device_event("device_updated", {
            **state.known_devices.get(ip, {"ip": ip}),
            **result,
        })

    elif command == "get_status":
        await ws_client.send_heartbeat()

    else:
        logger.warning(f"Unknown command: {command}")


# ---- Main Entry Point ----

async def main():
    setup_logging()
    logger.info(f"NetScout Agent starting (ID={AGENT_ID})")

    state = AgentState()
    ws_client = AgentWebSocketClient()

    # Register command handler
    async def on_command(message):
        await handle_backend_command(message, state, ws_client)

    ws_client.on_command(on_command)

    # Set up scheduler for periodic scans
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        lambda: asyncio.create_task(run_full_scan(state, ws_client)),
        trigger="interval",
        seconds=SCAN_INTERVAL_SECONDS,
        id="periodic_scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    # Run initial scan after a short delay (let WS connect first)
    async def initial_scan():
        await asyncio.sleep(5)
        await run_full_scan(state, ws_client)

    # Heartbeat task
    async def heartbeat_loop():
        while True:
            await asyncio.sleep(30)
            try:
                await ws_client.send_heartbeat()
            except Exception:
                pass

    # Launch everything
    await asyncio.gather(
        ws_client.connect_and_run(),
        initial_scan(),
        heartbeat_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user")
        sys.exit(0)
