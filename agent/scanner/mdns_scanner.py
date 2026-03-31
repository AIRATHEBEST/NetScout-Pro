"""
mDNS / Bonjour / DNS-SD discovery.
Finds devices advertising services on the local network
(Apple devices, printers, Chromecast, etc.)
"""

import asyncio
import logging
import socket
import time
from typing import Dict, List

from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

from config import MDNS_TIMEOUT

logger = logging.getLogger(__name__)

# Common mDNS service types to browse
MDNS_SERVICE_TYPES = [
    "_http._tcp.local.",
    "_https._tcp.local.",
    "_ssh._tcp.local.",
    "_ftp._tcp.local.",
    "_sftp-ssh._tcp.local.",
    "_smb._tcp.local.",
    "_afpovertcp._tcp.local.",
    "_nfs._tcp.local.",
    "_printer._tcp.local.",
    "_ipp._tcp.local.",
    "_ipps._tcp.local.",
    "_pdl-datastream._tcp.local.",
    "_airplay._tcp.local.",
    "_raop._tcp.local.",
    "_googlecast._tcp.local.",
    "_spotify-connect._tcp.local.",
    "_homekit._tcp.local.",
    "_hap._tcp.local.",
    "_miio._udp.local.",
    "_workstation._tcp.local.",
    "_device-info._tcp.local.",
    "_apple-mobdev2._tcp.local.",
    "_rdlink._tcp.local.",
    "_companion-link._tcp.local.",
]


class MDNSListener:
    def __init__(self):
        self.devices: Dict[str, Dict] = {}  # ip -> device info

    def add_service(self, zc: Zeroconf, service_type: str, name: str):
        try:
            info = zc.get_service_info(service_type, name)
            if info is None:
                return

            addresses = info.parsed_addresses()
            if not addresses:
                return

            for ip in addresses:
                # Skip IPv6 for now
                if ":" in ip:
                    continue

                existing = self.devices.get(ip, {})
                services = existing.get("mdns_services", [])

                service_entry = {
                    "type": service_type,
                    "name": name,
                    "port": info.port,
                    "server": info.server,
                    "properties": {
                        k.decode() if isinstance(k, bytes) else k:
                        v.decode() if isinstance(v, bytes) else v
                        for k, v in (info.properties or {}).items()
                    },
                }
                services.append(service_entry)

                self.devices[ip] = {
                    "ip": ip,
                    "hostname": info.server.rstrip(".") if info.server else "",
                    "mdns_name": name,
                    "mdns_services": services,
                    "discovery_method": "mDNS",
                    "last_seen": time.time(),
                }

        except Exception as e:
            logger.debug(f"mDNS service info error for {name}: {e}")

    def remove_service(self, zc: Zeroconf, service_type: str, name: str):
        pass  # Device departure handled by main scanner

    def update_service(self, zc: Zeroconf, service_type: str, name: str):
        self.add_service(zc, service_type, name)


def scan_mdns(timeout: float = MDNS_TIMEOUT) -> List[Dict]:
    """
    Browse all known mDNS service types and collect device information.
    Returns list of discovered devices with their services.
    """
    logger.info(f"Starting mDNS scan (timeout={timeout}s)")
    listener = MDNSListener()
    browsers = []

    try:
        zc = Zeroconf()
        for service_type in MDNS_SERVICE_TYPES:
            try:
                browser = ServiceBrowser(zc, service_type, listener)
                browsers.append(browser)
            except Exception as e:
                logger.debug(f"Could not browse {service_type}: {e}")

        # Wait for responses
        time.sleep(timeout)

        zc.close()
    except OSError as e:
        logger.warning(f"mDNS scan failed (may need multicast support): {e}")
        return []
    except Exception as e:
        logger.error(f"mDNS scan error: {e}")
        return []

    devices = list(listener.devices.values())
    logger.info(f"mDNS found {len(devices)} devices")
    return devices


def enrich_device_with_mdns(device: Dict, mdns_devices: List[Dict]) -> Dict:
    """
    Merge mDNS information into a device discovered by ARP/ICMP.
    """
    ip = device.get("ip")
    mdns_match = next((d for d in mdns_devices if d["ip"] == ip), None)
    if not mdns_match:
        return device

    # Enrich hostname if we didn't have one
    if not device.get("hostname") and mdns_match.get("hostname"):
        device["hostname"] = mdns_match["hostname"]

    device["mdns_name"] = mdns_match.get("mdns_name", "")
    device["mdns_services"] = mdns_match.get("mdns_services", [])

    # Try to infer device type from mDNS services
    if device.get("device_type", "unknown") == "unknown":
        device["device_type"] = _infer_type_from_mdns(mdns_match["mdns_services"])

    return device


def _infer_type_from_mdns(services: List[Dict]) -> str:
    """Guess device type from mDNS service types."""
    types = " ".join(s.get("type", "") for s in services).lower()

    if "_airplay" in types or "_raop" in types or "_apple-mobdev" in types:
        return "apple_device"
    if "_googlecast" in types:
        return "chromecast"
    if "_homekit" in types or "_hap" in types:
        return "smart_home"
    if "_printer" in types or "_ipp" in types or "_pdl" in types:
        return "printer"
    if "_ssh" in types:
        return "server"
    if "_smb" in types or "_afp" in types:
        return "nas_or_pc"
    if "_workstation" in types:
        return "workstation"

    return "unknown"
