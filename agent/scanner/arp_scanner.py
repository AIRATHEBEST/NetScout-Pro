"""
ARP + ICMP network discovery scanner.
Sends ARP requests across the subnet and collects replies.
Falls back to ICMP ping sweep for hosts that don't respond to ARP.
"""

import asyncio
import ipaddress
import logging
import socket
import struct
import subprocess
import time
from typing import List, Dict, Optional

import netifaces
import psutil
from scapy.all import ARP, Ether, srp, ICMP, IP, sr1
from netaddr import IPNetwork, IPAddress

from config import (
    NETWORK_INTERFACE,
    NETWORK_CIDR,
    ARP_TIMEOUT,
    PING_TIMEOUT,
)

logger = logging.getLogger(__name__)


def get_default_interface() -> Optional[str]:
    """Auto-detect the primary network interface."""
    try:
        gateways = netifaces.gateways()
        default = gateways.get("default", {})
        if netifaces.AF_INET in default:
            return default[netifaces.AF_INET][1]
    except Exception:
        pass

    # Fallback: pick first non-loopback interface with an IPv4 address
    for iface in netifaces.interfaces():
        if iface == "lo":
            continue
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            return iface
    return None


def get_network_cidr(interface: str) -> Optional[str]:
    """Derive network CIDR from interface IP + netmask."""
    try:
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET not in addrs:
            return None
        info = addrs[netifaces.AF_INET][0]
        ip = info["addr"]
        netmask = info["netmask"]

        # Convert to CIDR notation
        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        return str(network)
    except Exception as e:
        logger.error(f"Failed to get network CIDR for {interface}: {e}")
        return None


def get_local_ip(interface: str) -> Optional[str]:
    """Get the local IP of the given interface."""
    try:
        addrs = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addrs:
            return addrs[netifaces.AF_INET][0]["addr"]
    except Exception:
        pass
    return None


def arp_scan(network_cidr: str, interface: str) -> List[Dict]:
    """
    Perform ARP scan across the network.
    Returns list of {ip, mac, hostname} dicts.
    """
    logger.info(f"Starting ARP scan on {network_cidr} via {interface}")
    discovered = []

    try:
        arp_request = ARP(pdst=network_cidr)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        arp_request_broadcast = broadcast / arp_request

        answered, _ = srp(
            arp_request_broadcast,
            timeout=ARP_TIMEOUT,
            iface=interface,
            verbose=False,
            retry=2,
        )

        for sent, received in answered:
            ip = received.psrc
            mac = received.hwsrc.lower()
            hostname = _resolve_hostname(ip)

            discovered.append({
                "ip": ip,
                "mac": mac,
                "hostname": hostname,
                "discovery_method": "ARP",
                "last_seen": time.time(),
                "is_online": True,
            })

        logger.info(f"ARP scan found {len(discovered)} devices")
    except Exception as e:
        logger.error(f"ARP scan failed: {e}")
        # Try fallback method if scapy fails (e.g., no root)
        discovered = _arp_scan_fallback(network_cidr)

    return discovered


def _arp_scan_fallback(network_cidr: str) -> List[Dict]:
    """
    Fallback ARP scan using system 'arp-scan' command if available,
    or parsing the system ARP cache after a ping sweep.
    """
    logger.info("Using ARP fallback (system arp-scan or arp cache)")
    discovered = []

    try:
        # Try arp-scan tool
        result = subprocess.run(
            ["arp-scan", "--localnet", "--ignoredups"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    ip = parts[0].strip()
                    mac = parts[1].strip().lower()
                    try:
                        ipaddress.IPv4Address(ip)
                        discovered.append({
                            "ip": ip,
                            "mac": mac,
                            "hostname": _resolve_hostname(ip),
                            "discovery_method": "ARP_SCAN_TOOL",
                            "last_seen": time.time(),
                            "is_online": True,
                        })
                    except ValueError:
                        continue
            return discovered
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Final fallback: ping sweep then read ARP cache
    _ping_sweep(network_cidr)
    return _read_arp_cache()


def _ping_sweep(network_cidr: str):
    """Send ICMP pings to all hosts in subnet to populate ARP cache."""
    try:
        net = IPNetwork(network_cidr)
        hosts = list(net.iter_hosts())
        logger.info(f"Ping sweeping {len(hosts)} hosts")

        # Use subprocess ping for portability
        procs = []
        for host in hosts[:254]:  # cap at /24 equivalent
            proc = subprocess.Popen(
                ["ping", "-c", "1", "-W", "1", str(host)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            procs.append(proc)

        for proc in procs:
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception as e:
        logger.error(f"Ping sweep error: {e}")


def _read_arp_cache() -> List[Dict]:
    """Parse the system ARP cache."""
    discovered = []
    try:
        result = subprocess.run(
            ["arp", "-n"], capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines()[1:]:  # skip header
            parts = line.split()
            if len(parts) >= 3:
                ip = parts[0]
                mac = parts[2].lower()
                if mac not in ("(incomplete)", "<incomplete>"):
                    try:
                        ipaddress.IPv4Address(ip)
                        discovered.append({
                            "ip": ip,
                            "mac": mac,
                            "hostname": _resolve_hostname(ip),
                            "discovery_method": "ARP_CACHE",
                            "last_seen": time.time(),
                            "is_online": True,
                        })
                    except ValueError:
                        continue
    except Exception as e:
        logger.error(f"ARP cache read error: {e}")
    return discovered


def icmp_scan(network_cidr: str, known_ips: List[str]) -> List[Dict]:
    """
    ICMP ping sweep for hosts not found by ARP.
    Useful for hosts that filter ARP but respond to ICMP.
    """
    logger.info("Running ICMP sweep for missed hosts")
    discovered = []
    known_set = set(known_ips)

    try:
        net = IPNetwork(network_cidr)
        hosts = [str(h) for h in net.iter_hosts() if str(h) not in known_set]

        for ip in hosts:
            try:
                pkt = IP(dst=ip) / ICMP()
                reply = sr1(pkt, timeout=PING_TIMEOUT, verbose=False)
                if reply is not None:
                    discovered.append({
                        "ip": ip,
                        "mac": _get_mac_from_arp(ip),
                        "hostname": _resolve_hostname(ip),
                        "discovery_method": "ICMP",
                        "last_seen": time.time(),
                        "is_online": True,
                    })
            except Exception:
                continue
    except Exception as e:
        logger.error(f"ICMP scan error: {e}")

    logger.info(f"ICMP sweep found {len(discovered)} additional devices")
    return discovered


def _resolve_hostname(ip: str) -> str:
    """Reverse DNS lookup with timeout."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return ""


def _get_mac_from_arp(ip: str) -> str:
    """Try to get MAC address from system ARP cache for a given IP."""
    try:
        result = subprocess.run(
            ["arp", "-n", ip], capture_output=True, text=True, timeout=2
        )
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] not in ("(incomplete)", "<incomplete>"):
                return parts[2].lower()
    except Exception:
        pass
    return "00:00:00:00:00:00"


def discover_network() -> Dict:
    """
    Main entry point. Auto-detects interface + CIDR and runs full discovery.
    Returns { interface, network_cidr, local_ip, devices: [...] }
    """
    interface = NETWORK_INTERFACE or get_default_interface()
    if not interface:
        raise RuntimeError("Could not detect network interface")

    cidr = NETWORK_CIDR or get_network_cidr(interface)
    if not cidr:
        raise RuntimeError(f"Could not determine network CIDR for {interface}")

    local_ip = get_local_ip(interface)
    logger.info(f"Discovering on interface={interface}, cidr={cidr}, local_ip={local_ip}")

    # ARP scan (primary)
    devices = arp_scan(cidr, interface)

    # ICMP sweep for stragglers (skip if large subnet to save time)
    net = IPNetwork(cidr)
    if net.size <= 256:
        known_ips = [d["ip"] for d in devices]
        icmp_devices = icmp_scan(cidr, known_ips)
        devices.extend(icmp_devices)

    # Deduplicate by IP (keep ARP entry if duplicate)
    seen = {}
    for device in devices:
        ip = device["ip"]
        if ip not in seen:
            seen[ip] = device

    return {
        "interface": interface,
        "network_cidr": cidr,
        "local_ip": local_ip,
        "devices": list(seen.values()),
        "scan_time": time.time(),
    }
