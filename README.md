# 📡 NetScout — Network Scanning Platform

A real, production-grade Fing-style network scanner.  
Real ARP/ICMP/nmap scanning · Real-time WebSocket dashboard · No mock data.

---

## Architecture

```
[Local Network Agent] ──WS──► [FastAPI Backend] ◄──WS──► [React Dashboard]
       │                              │
  Real ARP/ICMP/nmap            PostgreSQL + Redis
  MAC vendor lookup
  mDNS discovery
  Port scanning
  Vuln detection
```

---

## Prerequisites

- Docker + Docker Compose
- The **agent** must run on a machine physically connected to the network you want to scan
- nmap must be available (it's installed automatically inside the agent Docker container)
- Root / NET_ADMIN capability required for ARP scanning (handled by Docker)

---

## Quick Start

### 1. Clone & configure

```bash
git clone <your-repo>
cd netscout

cp .env.example .env
# Edit .env — at minimum change AGENT_TOKEN and SECRET_KEY
```

### 2. Start everything

```bash
cd docker
docker compose up --build
```

Services start in order:
- PostgreSQL (port 5432)
- Redis (port 6379)  
- Backend API (port 8000)
- Frontend dashboard (port 3000)
- Agent (host networking)

### 3. Open the dashboard

```
http://localhost:3000
```

The agent starts scanning automatically after 5 seconds.  
Watch devices appear in real-time in the dashboard. ✅

---

## Running the Agent Separately (Recommended for Production)

The agent should run on a machine *inside* the target network.  
The backend can run anywhere (cloud, VPS, etc.).

```bash
cd agent

# Install dependencies
pip install -r requirements.txt

# Configure
cp ../.env.example .env
# Edit .env:
#   BACKEND_WS_URL=ws://your-backend-host:8000/ws/agent
#   AGENT_TOKEN=your-secret-token

# Run (requires root for ARP/ICMP scanning)
sudo python main.py
```

Or with Docker on the target machine:

```bash
docker build -t netscout-agent .
docker run --rm \
  --network host \
  --cap-add NET_ADMIN \
  --cap-add NET_RAW \
  -e BACKEND_WS_URL=ws://your-backend:8000/ws/agent \
  -e AGENT_TOKEN=your-secret-token \
  netscout-agent
```

---

## API Reference

### Base URL: `http://localhost:8000`
### Interactive docs: `http://localhost:8000/docs`

#### Devices

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all devices (supports `?is_online=true`, `?search=`, `?agent_id=`) |
| GET | `/api/devices/{id}` | Get single device |
| PATCH | `/api/devices/{id}` | Update name, tags, notes, trust |
| GET | `/api/devices/{id}/ports` | Get open ports |
| GET | `/api/devices/{id}/vulnerabilities` | Get vulnerability findings |
| GET | `/api/devices/stats/summary` | Network summary stats |

#### Scans & Alerts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/scans` | Scan history |
| GET | `/api/alerts` | Security alerts |
| POST | `/api/alerts/{id}/acknowledge` | Acknowledge alert |
| GET | `/api/agents` | Connected agents |
| POST | `/api/agents/{id}/scan` | Trigger immediate scan |
| POST | `/api/agents/{id}/deep-scan?ip=x.x.x.x` | Trigger deep nmap scan on IP |

#### WebSocket: `/ws/dashboard`

Connect from any client. Messages you receive:

```json
{ "type": "scan_result",    "agent_id": "...", "data": { "devices": [...], "stats": {...} } }
{ "type": "device_joined",  "agent_id": "...", "device": {...} }
{ "type": "device_left",    "agent_id": "...", "device": {...} }
{ "type": "device_updated", "agent_id": "...", "device": {...} }
{ "type": "alert",          "agent_id": "...", "alert": {...}  }
{ "type": "agent_status",   "agent_id": "...", "status": "online|offline" }
```

Commands you can send:

```json
{ "type": "trigger_scan", "agent_id": "agent-001" }
{ "type": "deep_scan",    "agent_id": "agent-001", "ip": "192.168.1.1" }
```

---

## What the Agent Scans

| Method | What it finds |
|--------|--------------|
| ARP (scapy) | All devices on subnet — IP + MAC |
| ICMP ping sweep | Devices that block ARP but respond to ping |
| mDNS/Bonjour | Apple, Chromecast, printers, smart home devices |
| nmap TCP (top 1000 ports) | Open ports, service versions, banners |
| nmap OS detection | OS name, family, accuracy |
| MAC OUI lookup | Vendor/manufacturer name |
| Vulnerability checks | Telnet, FTP, SMB, RDP, VNC, Redis, MongoDB exposure |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_TOKEN` | `change-me` | Shared secret between agent and backend |
| `SECRET_KEY` | `change-me` | JWT signing key |
| `AGENT_ID` | `agent-001` | Unique agent identifier |
| `BACKEND_WS_URL` | `ws://localhost:8000/ws/agent` | Backend WebSocket URL |
| `SCAN_INTERVAL_SECONDS` | `60` | How often to scan (seconds) |
| `ENABLE_PORT_SCAN` | `true` | Enable nmap port scanning |
| `ENABLE_OS_DETECTION` | `true` | Enable OS fingerprinting (slower) |
| `ENABLE_MDNS` | `true` | Enable mDNS/Bonjour discovery |
| `NETWORK_INTERFACE` | auto | Force specific interface (e.g. `eth0`) |
| `NETWORK_CIDR` | auto | Force specific subnet (e.g. `192.168.1.0/24`) |
| `PORT_SCAN_TOP_PORTS` | `1000` | How many ports nmap scans |

---

## Production Deployment

### 1. Secure your tokens

```bash
# Generate strong tokens
openssl rand -hex 32   # for AGENT_TOKEN
openssl rand -hex 32   # for SECRET_KEY
```

### 2. Run backend on a cloud server (e.g. Ubuntu VPS)

```bash
cd docker
docker compose up -d postgres redis backend frontend
```

### 3. Run agent on each local network

```bash
# On each target network machine:
docker run -d \
  --network host \
  --cap-add NET_ADMIN --cap-add NET_RAW \
  --restart unless-stopped \
  -e BACKEND_WS_URL=ws://YOUR_SERVER_IP:8000/ws/agent \
  -e AGENT_TOKEN=your-strong-token \
  -e AGENT_ID=office-network \
  netscout-agent
```

### 4. Put backend behind a reverse proxy (nginx/caddy) with HTTPS

Use Caddy for automatic TLS:

```
your-domain.com {
  reverse_proxy localhost:8000
}
```

Then set `BACKEND_WS_URL=wss://your-domain.com/ws/agent` on the agent.

---

## Folder Structure

```
netscout/
├── agent/                  # Python scanning agent
│   ├── main.py             # Orchestrator + scheduler
│   ├── scanner/
│   │   ├── arp_scanner.py  # ARP + ICMP discovery
│   │   ├── nmap_scanner.py # Port + OS fingerprinting
│   │   ├── mdns_scanner.py # mDNS/Bonjour discovery
│   │   └── mac_vendor.py   # MAC OUI lookup
│   └── transport/
│       └── ws_client.py    # WebSocket client to backend
├── backend/                # FastAPI backend
│   ├── main.py
│   ├── api/
│   │   ├── devices.py      # Device CRUD endpoints
│   │   ├── scans.py        # Scan/alert endpoints
│   │   └── ws.py           # WebSocket hub
│   ├── models/             # SQLAlchemy models
│   └── db/                 # Database + Redis clients
├── frontend/               # React + Vite dashboard
│   └── src/
│       ├── App.jsx         # Main app with stats + live updates
│       ├── components/     # DeviceTable, DeviceCard, PortList, Alerts
│       ├── hooks/          # useWebSocket, useDevices
│       └── api/client.js   # REST API client
└── docker/
    └── docker-compose.yml  # Full stack orchestration
```

---

## Next Steps (Phase 2)

- Speed test integration (Cloudflare/Ookla API)
- Network topology graph (D3.js force layout)
- Email/push notification integration
- Multi-network management (multiple agents)
- React Native mobile app
- User authentication (login/multi-user)
- Historical device timeline graphs
