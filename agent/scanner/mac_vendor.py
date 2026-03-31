"""
MAC address vendor (OUI) lookup.
Uses a local cached database first, falls back to API.
"""

import json
import logging
import os
import time
from typing import Optional

import requests

from config import MAC_VENDOR_API, MAC_VENDOR_CACHE_TTL

logger = logging.getLogger(__name__)

CACHE_FILE = "/tmp/mac_vendor_cache.json"
_cache: dict = {}
_cache_loaded = False


def _load_cache():
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    _cache_loaded = True


def _save_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f)
    except Exception as e:
        logger.debug(f"Failed to save MAC cache: {e}")


def lookup_vendor(mac: str) -> str:
    """
    Look up the vendor/manufacturer for a MAC address.
    Uses local cache first, then online API.
    Returns vendor string or empty string if unknown.
    """
    if not mac or mac == "00:00:00:00:00:00":
        return ""

    # Normalize MAC to uppercase, colon-separated
    mac_clean = mac.upper().replace("-", ":").replace(".", ":")

    # OUI is first 3 octets
    oui = ":".join(mac_clean.split(":")[:3])

    _load_cache()

    # Check cache
    cached = _cache.get(oui)
    if cached:
        # Check TTL
        if time.time() - cached.get("ts", 0) < MAC_VENDOR_CACHE_TTL:
            return cached.get("vendor", "")

    # Query API
    vendor = _fetch_vendor_from_api(mac_clean)

    # Cache the result
    _cache[oui] = {"vendor": vendor, "ts": time.time()}
    _save_cache()

    return vendor


def _fetch_vendor_from_api(mac: str) -> str:
    """Query macvendors.com API for vendor info."""
    try:
        response = requests.get(
            f"{MAC_VENDOR_API}/{mac}",
            timeout=5,
            headers={"User-Agent": "NetScout-Agent/1.0"},
        )
        if response.status_code == 200:
            return response.text.strip()
        elif response.status_code == 404:
            return "Unknown"
        else:
            logger.debug(f"MAC vendor API returned {response.status_code} for {mac}")
            return ""
    except requests.exceptions.Timeout:
        logger.debug(f"MAC vendor lookup timeout for {mac}")
        return ""
    except Exception as e:
        logger.debug(f"MAC vendor lookup error for {mac}: {e}")
        return ""


def batch_lookup(macs: list) -> dict:
    """
    Lookup vendors for multiple MACs.
    Returns dict of {mac: vendor}.
    """
    results = {}
    for mac in macs:
        results[mac] = lookup_vendor(mac)
        # Small delay to be polite to the API
        time.sleep(0.1)
    return results


# Offline fallback: common well-known OUI prefixes
WELL_KNOWN_OUIS = {
    "00:50:56": "VMware",
    "00:0C:29": "VMware",
    "00:15:5D": "Microsoft Hyper-V",
    "08:00:27": "VirtualBox",
    "52:54:00": "QEMU/KVM",
    "00:1A:11": "Google",
    "F8:8F:CA": "Apple",
    "AC:BC:32": "Apple",
    "3C:22:FB": "Apple",
    "00:17:F2": "Apple",
    "B8:27:EB": "Raspberry Pi Foundation",
    "DC:A6:32": "Raspberry Pi Foundation",
    "E4:5F:01": "Raspberry Pi Foundation",
    "CC:F9:E8": "Raspberry Pi Foundation",
    "18:FE:34": "Espressif (ESP8266/ESP32)",
    "AC:67:B2": "Espressif",
    "24:6F:28": "Espressif",
    "A4:CF:12": "Espressif",
    "00:1E:C2": "Apple Airport",
    "00:03:7F": "Atheros",
    "00:14:22": "Dell",
    "00:21:70": "Dell",
    "D4:BE:D9": "Dell",
    "00:0D:3A": "Microsoft",
    "00:17:FA": "Microsoft",
    "FC:44:82": "Cisco",
    "00:00:0C": "Cisco",
    "00:1B:54": "Cisco",
    "00:50:C2": "IEEE",
}


def lookup_vendor_offline(mac: str) -> str:
    """Quick offline lookup using known OUI prefixes."""
    if not mac:
        return ""
    mac_upper = mac.upper().replace("-", ":").replace(".", ":")
    oui = ":".join(mac_upper.split(":")[:3])
    return WELL_KNOWN_OUIS.get(oui, "")
