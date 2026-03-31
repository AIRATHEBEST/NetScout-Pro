"""
nmap-based port scanning, service detection, OS fingerprinting,
and banner grabbing for discovered devices.
"""

import logging
import socket
import time
from typing import Dict, List, Optional

import nmap

from config import PORT_SCAN_TOP_PORTS, ENABLE_OS_DETECTION

logger = logging.getLogger(__name__)

# Well-known service risk levels
HIGH_RISK_PORTS = {21, 23, 445, 1433, 1521, 3306, 3389, 5900, 6379, 27017}
MEDIUM_RISK_PORTS = {22, 25, 80, 110, 143, 389, 443, 8080, 8443}


def scan_device(ip: str, top_ports: int = PORT_SCAN_TOP_PORTS) -> Dict:
    """
    Full nmap scan on a single device:
    - TCP SYN scan (top N ports)
    - Service + version detection
    - OS detection (if enabled and running as root)
    - Script scanning for common vulns (safe scripts only)

    Returns enriched device dict.
    """
    logger.info(f"Port scanning {ip} (top {top_ports} ports)")
    nm = nmap.PortScanner()

    # Build nmap arguments
    args = f"-sV --version-intensity 5 --top-ports {top_ports} -T4 --open"
    if ENABLE_OS_DETECTION:
        args += " -O --osscan-guess"
    # Safe NSE scripts for service info
    args += " --script=banner,http-title,smb-os-discovery,dns-service-discovery"

    result = {
        "ip": ip,
        "ports": [],
        "os_info": {},
        "device_type": "unknown",
        "scan_time": time.time(),
    }

    try:
        nm.scan(hosts=ip, arguments=args, sudo=ENABLE_OS_DETECTION)

        if ip not in nm.all_hosts():
            logger.warning(f"nmap found no data for {ip}")
            return result

        host = nm[ip]

        # --- Parse open ports ---
        for proto in host.all_protocols():
            for port, port_data in host[proto].items():
                if port_data["state"] == "open":
                    service = {
                        "port": port,
                        "protocol": proto,
                        "state": port_data["state"],
                        "service": port_data.get("name", "unknown"),
                        "product": port_data.get("product", ""),
                        "version": port_data.get("version", ""),
                        "extrainfo": port_data.get("extrainfo", ""),
                        "cpe": port_data.get("cpe", ""),
                        "banner": _extract_banner(port_data),
                        "risk_level": _assess_port_risk(port),
                    }
                    result["ports"].append(service)

        # Sort by port number
        result["ports"].sort(key=lambda x: x["port"])

        # --- OS Detection ---
        if ENABLE_OS_DETECTION and "osmatch" in host:
            os_matches = host["osmatch"]
            if os_matches:
                best = os_matches[0]
                result["os_info"] = {
                    "name": best.get("name", ""),
                    "accuracy": int(best.get("accuracy", 0)),
                    "os_family": _extract_os_family(best),
                    "os_gen": best.get("osclass", [{}])[0].get("osgen", ""),
                    "vendor": best.get("osclass", [{}])[0].get("vendor", ""),
                    "all_matches": [
                        {"name": m.get("name"), "accuracy": m.get("accuracy")}
                        for m in os_matches[:3]
                    ],
                }
                result["device_type"] = _classify_device_type(
                    result["os_info"], result["ports"]
                )

        # --- Device type from services if no OS ---
        if result["device_type"] == "unknown":
            result["device_type"] = _classify_from_ports(result["ports"])

        logger.info(
            f"Scan complete for {ip}: {len(result['ports'])} open ports, "
            f"OS={result['os_info'].get('name', 'unknown')}"
        )

    except nmap.PortScannerError as e:
        logger.error(f"nmap error scanning {ip}: {e}")
    except Exception as e:
        logger.error(f"Unexpected scan error for {ip}: {e}")

    return result


def quick_scan(ip: str) -> Dict:
    """
    Fast scan: top 100 ports, no OS detection, no scripts.
    Used for newly discovered devices to get quick info.
    """
    logger.info(f"Quick scan on {ip}")
    nm = nmap.PortScanner()
    result = {"ip": ip, "ports": [], "os_info": {}, "device_type": "unknown"}

    try:
        nm.scan(hosts=ip, arguments="--top-ports 100 -T4 --open -sV")
        if ip not in nm.all_hosts():
            return result

        host = nm[ip]
        for proto in host.all_protocols():
            for port, port_data in host[proto].items():
                if port_data["state"] == "open":
                    result["ports"].append({
                        "port": port,
                        "protocol": proto,
                        "state": "open",
                        "service": port_data.get("name", "unknown"),
                        "product": port_data.get("product", ""),
                        "version": port_data.get("version", ""),
                        "risk_level": _assess_port_risk(port),
                    })

        result["device_type"] = _classify_from_ports(result["ports"])

    except Exception as e:
        logger.error(f"Quick scan error for {ip}: {e}")

    return result


def udp_scan(ip: str, ports: str = "53,67,68,69,123,161,162,500,1900") -> List[Dict]:
    """
    UDP scan for common services: DNS, DHCP, TFTP, NTP, SNMP, SSDP.
    Requires root. Returns list of open UDP ports.
    """
    logger.info(f"UDP scan on {ip}")
    nm = nmap.PortScanner()
    udp_ports = []

    try:
        nm.scan(hosts=ip, arguments=f"-sU -p {ports} -T4 --open", sudo=True)
        if ip not in nm.all_hosts():
            return udp_ports

        host = nm[ip]
        if "udp" in host.all_protocols():
            for port, port_data in host["udp"].items():
                if port_data["state"] in ("open", "open|filtered"):
                    udp_ports.append({
                        "port": port,
                        "protocol": "udp",
                        "state": port_data["state"],
                        "service": port_data.get("name", "unknown"),
                        "risk_level": _assess_port_risk(port),
                    })
    except Exception as e:
        logger.error(f"UDP scan error for {ip}: {e}")

    return udp_ports


def check_vulnerability_indicators(ip: str, ports: List[Dict]) -> List[Dict]:
    """
    Check for common vulnerability indicators based on open ports + service versions.
    Returns list of vulnerability findings.
    """
    vulns = []
    open_ports = {p["port"] for p in ports}

    # Telnet open (insecure)
    if 23 in open_ports:
        vulns.append({
            "severity": "HIGH",
            "title": "Telnet Service Exposed",
            "description": "Telnet transmits data in plaintext including credentials.",
            "port": 23,
            "recommendation": "Disable Telnet, use SSH instead.",
        })

    # FTP open
    if 21 in open_ports:
        ftp_port = next((p for p in ports if p["port"] == 21), {})
        vulns.append({
            "severity": "MEDIUM",
            "title": "FTP Service Exposed",
            "description": f"FTP service detected: {ftp_port.get('product', '')} {ftp_port.get('version', '')}. May allow anonymous access.",
            "port": 21,
            "recommendation": "Use SFTP/FTPS. Disable anonymous FTP.",
        })

    # SMB open (potential EternalBlue)
    if 445 in open_ports:
        vulns.append({
            "severity": "HIGH",
            "title": "SMB Service Exposed",
            "description": "SMB (port 445) is exposed. Could be vulnerable to exploits like EternalBlue.",
            "port": 445,
            "recommendation": "Ensure Windows is fully patched. Block SMB at network boundary.",
        })

    # RDP open
    if 3389 in open_ports:
        vulns.append({
            "severity": "HIGH",
            "title": "RDP Service Exposed",
            "description": "Remote Desktop Protocol is exposed to the network.",
            "port": 3389,
            "recommendation": "Restrict RDP access via firewall. Use VPN for remote access.",
        })

    # VNC open
    if 5900 in open_ports or 5901 in open_ports:
        vulns.append({
            "severity": "HIGH",
            "title": "VNC Service Exposed",
            "description": "VNC remote desktop is exposed.",
            "port": 5900,
            "recommendation": "Restrict VNC with strong passwords and firewall rules.",
        })

    # Redis without auth
    if 6379 in open_ports:
        vulns.append({
            "severity": "CRITICAL",
            "title": "Redis Port Exposed",
            "description": "Redis (6379) is exposed. Default Redis has no authentication.",
            "port": 6379,
            "recommendation": "Enable Redis AUTH, bind to localhost, or firewall this port.",
        })

    # MongoDB
    if 27017 in open_ports:
        vulns.append({
            "severity": "CRITICAL",
            "title": "MongoDB Port Exposed",
            "description": "MongoDB (27017) is exposed on the network.",
            "port": 27017,
            "recommendation": "Enable MongoDB authentication and restrict network access.",
        })

    return vulns


# ---- Internal helpers ----

def _extract_banner(port_data: Dict) -> str:
    """Extract banner from nmap script output."""
    script = port_data.get("script", {})
    if "banner" in script:
        return script["banner"][:500]  # cap length
    if "http-title" in script:
        return f"HTTP Title: {script['http-title']}"
    return ""


def _assess_port_risk(port: int) -> str:
    if port in HIGH_RISK_PORTS:
        return "HIGH"
    if port in MEDIUM_RISK_PORTS:
        return "MEDIUM"
    return "LOW"


def _extract_os_family(os_match: Dict) -> str:
    osclass = os_match.get("osclass", [])
    if osclass:
        return osclass[0].get("osfamily", "")
    return ""


def _classify_device_type(os_info: Dict, ports: List[Dict]) -> str:
    """Classify device based on OS + ports."""
    os_name = os_info.get("name", "").lower()
    os_family = os_info.get("os_family", "").lower()

    if "ios" in os_name or "iphone" in os_name or "ipad" in os_name:
        return "mobile"
    if "android" in os_name:
        return "mobile"
    if "windows" in os_family or "windows" in os_name:
        return "windows_pc"
    if "linux" in os_family or "ubuntu" in os_name or "debian" in os_name:
        open_ports = {p["port"] for p in ports}
        if 80 in open_ports or 443 in open_ports or 8080 in open_ports:
            return "server"
        return "linux_pc"
    if "mac" in os_family or "macos" in os_name or "os x" in os_name:
        return "mac"
    if "embedded" in os_family or "broadband" in os_name:
        return "router"

    return _classify_from_ports(ports)


def _classify_from_ports(ports: List[Dict]) -> str:
    """Guess device type from open services."""
    open_services = {p.get("service", "").lower() for p in ports}
    open_ports = {p["port"] for p in ports}

    if "printer" in open_services or 9100 in open_ports:
        return "printer"
    if 554 in open_ports or "rtsp" in open_services:
        return "camera"
    if "upnp" in open_services or 1900 in open_ports:
        return "smart_device"
    if 80 in open_ports or 443 in open_ports:
        if 22 in open_ports:
            return "server"
        return "web_device"
    if 22 in open_ports:
        return "server"
    if 3389 in open_ports:
        return "windows_pc"

    return "unknown"
