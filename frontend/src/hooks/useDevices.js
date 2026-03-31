import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';

export function useDevices(agentId = null) {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchDevices = useCallback(async () => {
    try {
      setLoading(true);
      const params = agentId ? { agent_id: agentId, limit: 500 } : { limit: 500 };
      const data = await api.getDevices(params);
      setDevices(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  // Apply a live WebSocket update to the device list
  const applyEvent = useCallback((eventType, deviceData) => {
    const ip = deviceData?.ip;
    if (!ip) return;

    setDevices((prev) => {
      switch (eventType) {
        case 'device_joined': {
          const exists = prev.find((d) => d.ip === ip);
          if (exists) {
            return prev.map((d) => d.ip === ip ? { ...d, ...deviceData, is_online: true } : d);
          }
          return [{ ...deviceData, is_online: true }, ...prev];
        }
        case 'device_left':
          return prev.map((d) => d.ip === ip ? { ...d, is_online: false } : d);
        case 'device_updated':
          return prev.map((d) => d.ip === ip ? { ...d, ...deviceData } : d);
        case 'scan_result': {
          // Full scan result: upsert all devices
          const incoming = deviceData?.devices || [];
          const incomingMap = Object.fromEntries(incoming.map((d) => [d.ip, d]));
          const updated = prev.map((d) => incomingMap[d.ip] ? { ...d, ...incomingMap[d.ip] } : d);
          const existingIps = new Set(prev.map((d) => d.ip));
          const newOnes = incoming.filter((d) => !existingIps.has(d.ip));
          return [...newOnes, ...updated];
        }
        default:
          return prev;
      }
    });
  }, []);

  return { devices, loading, error, refetch: fetchDevices, applyEvent };
}
