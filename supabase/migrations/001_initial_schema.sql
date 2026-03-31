-- ============================================================
-- NetScout Pro — Initial Schema
-- Run this in your Supabase SQL Editor:
-- https://supabase.com/dashboard/project/jqteahtqwffjenserypk/sql
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────────────────────
-- AGENTS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    network_cidr    TEXT,
    interface       TEXT,
    version         TEXT,
    status          TEXT NOT NULL DEFAULT 'offline',   -- online | offline
    last_seen       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata        JSONB DEFAULT '{}'
);

-- ─────────────────────────────────────────────────────────────
-- SCANS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scans (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'running',   -- running | completed | failed
    scan_type       TEXT NOT NULL DEFAULT 'full',      -- full | quick | deep
    devices_found   INTEGER DEFAULT 0,
    devices_online  INTEGER DEFAULT 0,
    devices_new     INTEGER DEFAULT 0,
    duration_ms     INTEGER,
    error           TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    metadata        JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_scans_agent_id  ON scans(agent_id);
CREATE INDEX IF NOT EXISTS idx_scans_started_at ON scans(started_at DESC);

-- ─────────────────────────────────────────────────────────────
-- DEVICES
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS devices (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    ip_address      INET NOT NULL,
    mac_address     MACADDR,
    hostname        TEXT,
    vendor          TEXT,
    device_type     TEXT DEFAULT 'unknown',            -- router | computer | phone | printer | smart_tv | iot | unknown
    os_name         TEXT,
    os_family       TEXT,
    os_accuracy     INTEGER,
    custom_name     TEXT,
    notes           TEXT,
    tags            TEXT[] DEFAULT '{}',
    is_online       BOOLEAN NOT NULL DEFAULT FALSE,
    is_trusted      BOOLEAN NOT NULL DEFAULT FALSE,
    is_new          BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(agent_id, mac_address),
    UNIQUE(agent_id, ip_address)
);

CREATE INDEX IF NOT EXISTS idx_devices_agent_id   ON devices(agent_id);
CREATE INDEX IF NOT EXISTS idx_devices_ip         ON devices(ip_address);
CREATE INDEX IF NOT EXISTS idx_devices_mac        ON devices(mac_address);
CREATE INDEX IF NOT EXISTS idx_devices_is_online  ON devices(is_online);
CREATE INDEX IF NOT EXISTS idx_devices_last_seen  ON devices(last_seen DESC);

-- ─────────────────────────────────────────────────────────────
-- PORTS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ports (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    port            INTEGER NOT NULL,
    protocol        TEXT NOT NULL DEFAULT 'tcp',
    state           TEXT NOT NULL DEFAULT 'open',
    service         TEXT,
    version         TEXT,
    banner          TEXT,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(device_id, port, protocol)
);

CREATE INDEX IF NOT EXISTS idx_ports_device_id ON ports(device_id);
CREATE INDEX IF NOT EXISTS idx_ports_port      ON ports(port);

-- ─────────────────────────────────────────────────────────────
-- VULNERABILITIES
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vulnerabilities (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id       UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    port            INTEGER,
    service         TEXT,
    severity        TEXT NOT NULL DEFAULT 'medium',   -- critical | high | medium | low | info
    title           TEXT NOT NULL,
    description     TEXT,
    recommendation  TEXT,
    is_resolved     BOOLEAN NOT NULL DEFAULT FALSE,
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vulns_device_id  ON vulnerabilities(device_id);
CREATE INDEX IF NOT EXISTS idx_vulns_severity   ON vulnerabilities(severity);
CREATE INDEX IF NOT EXISTS idx_vulns_resolved   ON vulnerabilities(is_resolved);

-- ─────────────────────────────────────────────────────────────
-- ALERTS
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id        TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    device_id       UUID REFERENCES devices(id) ON DELETE SET NULL,
    alert_type      TEXT NOT NULL,   -- new_device | device_offline | vulnerability | port_opened | port_closed
    severity        TEXT NOT NULL DEFAULT 'info',   -- critical | high | medium | low | info
    title           TEXT NOT NULL,
    message         TEXT,
    is_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_agent_id    ON alerts(agent_id);
CREATE INDEX IF NOT EXISTS idx_alerts_device_id   ON alerts(device_id);
CREATE INDEX IF NOT EXISTS idx_alerts_type        ON alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_ack         ON alerts(is_acknowledged);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at  ON alerts(created_at DESC);

-- ─────────────────────────────────────────────────────────────
-- AUTO-UPDATE updated_at TRIGGER
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─────────────────────────────────────────────────────────────
-- REALTIME (enable for live dashboard updates)
-- ─────────────────────────────────────────────────────────────
ALTER PUBLICATION supabase_realtime ADD TABLE devices;
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
ALTER PUBLICATION supabase_realtime ADD TABLE scans;

-- ─────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY (optional — disable for internal use)
-- ─────────────────────────────────────────────────────────────
-- ALTER TABLE devices ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scans   ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE alerts  ENABLE ROW LEVEL SECURITY;

-- Done! ✅
SELECT 'NetScout Pro schema created successfully 🚀' AS status;
