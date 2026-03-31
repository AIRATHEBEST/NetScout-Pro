import os
from dotenv import load_dotenv

load_dotenv()

# Backend connection
BACKEND_WS_URL = os.getenv("BACKEND_WS_URL", "ws://localhost:8000/ws/agent")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "change-me-in-production")
AGENT_ID = os.getenv("AGENT_ID", "agent-001")

# Scan settings
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))
PORT_SCAN_TOP_PORTS = int(os.getenv("PORT_SCAN_TOP_PORTS", "1000"))
ENABLE_OS_DETECTION = os.getenv("ENABLE_OS_DETECTION", "true").lower() == "true"
ENABLE_PORT_SCAN = os.getenv("ENABLE_PORT_SCAN", "true").lower() == "true"
ENABLE_MDNS = os.getenv("ENABLE_MDNS", "true").lower() == "true"

# Network
NETWORK_INTERFACE = os.getenv("NETWORK_INTERFACE", "")  # auto-detect if empty
NETWORK_CIDR = os.getenv("NETWORK_CIDR", "")            # auto-detect if empty
ARP_TIMEOUT = float(os.getenv("ARP_TIMEOUT", "3.0"))
PING_TIMEOUT = float(os.getenv("PING_TIMEOUT", "1.0"))
MDNS_TIMEOUT = float(os.getenv("MDNS_TIMEOUT", "5.0"))

# MAC vendor DB (uses online API + local cache)
MAC_VENDOR_API = "https://api.macvendors.com"
MAC_VENDOR_CACHE_TTL = 86400  # 24 hours in seconds
