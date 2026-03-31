const BASE_URL = import.meta.env.VITE_API_URL || '';

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Devices
  getDevices: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/devices${qs ? '?' + qs : ''}`);
  },
  getDevice: (id) => request(`/api/devices/${id}`),
  updateDevice: (id, data) => request(`/api/devices/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  getDevicePorts: (id) => request(`/api/devices/${id}/ports`),
  getDeviceVulns: (id) => request(`/api/devices/${id}/vulnerabilities`),
  getStats: (agentId) => request(`/api/devices/stats/summary${agentId ? '?agent_id=' + agentId : ''}`),

  // Scans
  getScans: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/scans${qs ? '?' + qs : ''}`);
  },

  // Alerts
  getAlerts: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/api/alerts${qs ? '?' + qs : ''}`);
  },
  acknowledgeAlert: (id) => request(`/api/alerts/${id}/acknowledge`, { method: 'POST' }),

  // Agents
  getAgents: () => request('/api/agents'),
  triggerScan: (agentId) => request(`/api/agents/${agentId}/scan`, { method: 'POST' }),
  triggerDeepScan: (agentId, ip) =>
    request(`/api/agents/${agentId}/deep-scan?ip=${encodeURIComponent(ip)}`, { method: 'POST' }),
};
