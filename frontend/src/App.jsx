import { useState, useEffect, useCallback } from 'react';
import { Wifi, RefreshCw, ShieldAlert, Activity, Server, Search } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { useWebSocket } from './hooks/useWebSocket';
import { useDevices } from './hooks/useDevices';
import { DeviceTable } from './components/DeviceTable';
import { DeviceCard } from './components/DeviceCard';
import { AlertBanner } from './components/AlertBanner';
import { api } from './api/client';

const PIE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#6b7280'];

export default function App() {
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [search, setSearch] = useState('');
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [scanLogs, setScanLogs] = useState([]);
  const [agents, setAgents] = useState([]);
  const [lastScanTime, setLastScanTime] = useState(null);
  const [isScanning, setIsScanning] = useState(false);

  const { devices, loading, error, refetch, applyEvent } = useDevices();

  // Handle WebSocket messages
  const handleWsMessage = useCallback((msg) => {
    const { type } = msg;

    if (type === 'scan_result') {
      setIsScanning(false);
      setLastScanTime(new Date());
      applyEvent('scan_result', msg.data);
      // Refresh stats after scan
      api.getStats().then(setStats).catch(() => {});
      api.getScans({ limit: 10 }).then(setScanLogs).catch(() => {});
    } else if (type === 'device_joined') {
      applyEvent('device_joined', msg.device);
    } else if (type === 'device_left') {
      applyEvent('device_left', msg.device);
    } else if (type === 'device_updated') {
      applyEvent('device_updated', msg.device);
    } else if (type === 'alert') {
      setAlerts((prev) => [msg.alert, ...prev]);
    } else if (type === 'agent_status') {
      if (msg.status === 'online') {
        setAgents((prev) => prev.includes(msg.agent_id) ? prev : [...prev, msg.agent_id]);
      } else {
        setAgents((prev) => prev.filter((a) => a !== msg.agent_id));
      }
    }
  }, [applyEvent]);

  const { status: wsStatus, send: wsSend } = useWebSocket(handleWsMessage);

  // Initial data load
  useEffect(() => {
    api.getStats().then(setStats).catch(() => {});
    api.getAlerts({ unacknowledged_only: true, limit: 20 }).then(setAlerts).catch(() => {});
    api.getScans({ limit: 10 }).then(setScanLogs).catch(() => {});
    api.getAgents().then((data) => setAgents(data.connected_agents || [])).catch(() => {});
  }, []);

  const triggerScan = async () => {
    if (!agents.length) return;
    setIsScanning(true);
    try {
      await api.triggerScan(agents[0]);
    } catch (e) {
      setIsScanning(false);
    }
  };

  const handleDeepScan = async (ip) => {
    if (!agents.length) return;
    await api.triggerDeepScan(agents[0], ip);
  };

  const filteredDevices = search
    ? devices.filter((d) =>
        (d.ip || '').includes(search) ||
        (d.hostname || '').toLowerCase().includes(search.toLowerCase()) ||
        (d.vendor || '').toLowerCase().includes(search.toLowerCase()) ||
        (d.mac || '').toLowerCase().includes(search.toLowerCase()) ||
        (d.custom_name || '').toLowerCase().includes(search.toLowerCase())
      )
    : devices;

  // Build type distribution for pie chart
  const typeData = stats?.by_type
    ? Object.entries(stats.by_type).map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top nav */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
              <Wifi size={16} className="text-white" />
            </div>
            <span className="font-bold text-gray-900 text-lg">NetScout</span>
          </div>

          <div className="flex items-center gap-3">
            {/* WS status */}
            <div className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
              wsStatus === 'connected' ? 'bg-green-100 text-green-700' :
              wsStatus === 'connecting' ? 'bg-yellow-100 text-yellow-700' :
              'bg-red-100 text-red-700'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${
                wsStatus === 'connected' ? 'bg-green-500' :
                wsStatus === 'connecting' ? 'bg-yellow-500 animate-pulse' :
                'bg-red-500'
              }`} />
              {wsStatus}
            </div>

            {/* Agent status */}
            <div className={`flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
              agents.length > 0 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-500'
            }`}>
              <Server size={11} />
              {agents.length > 0 ? `${agents.length} agent${agents.length > 1 ? 's' : ''} online` : 'No agents'}
            </div>

            {/* Scan button */}
            <button
              onClick={triggerScan}
              disabled={!agents.length || isScanning}
              className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
            >
              <RefreshCw size={13} className={isScanning ? 'animate-spin' : ''} />
              {isScanning ? 'Scanning...' : 'Scan Now'}
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Alerts */}
        {alerts.filter((a) => !a.is_acknowledged).length > 0 && (
          <AlertBanner
            alerts={alerts}
            onAcknowledge={(id) =>
              setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, is_acknowledged: true } : a))
            }
          />
        )}

        {/* Stats row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Total Devices', value: stats?.total_devices ?? devices.length, icon: Wifi, color: 'blue' },
            { label: 'Online Now', value: stats?.online_devices ?? devices.filter((d) => d.is_online).length, icon: Activity, color: 'green' },
            { label: 'With Vulns', value: stats?.devices_with_vulnerabilities ?? 0, icon: ShieldAlert, color: 'red' },
            { label: 'Scan Logs', value: scanLogs.length, icon: RefreshCw, color: 'purple' },
          ].map(({ label, value, icon: Icon, color }) => (
            <div key={label} className="bg-white rounded-2xl p-4 border border-gray-100 shadow-sm">
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center mb-3 bg-${color}-50`}>
                <Icon size={16} className={`text-${color}-600`} />
              </div>
              <div className="text-2xl font-bold text-gray-900">{value ?? '—'}</div>
              <div className="text-xs text-gray-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>

        {/* Charts row */}
        {typeData.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Device type pie */}
            <div className="bg-white rounded-2xl p-4 border border-gray-100 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Device Types</h3>
              <div className="flex items-center gap-4">
                <ResponsiveContainer width="50%" height={140}>
                  <PieChart>
                    <Pie data={typeData} dataKey="value" cx="50%" cy="50%" innerRadius={35} outerRadius={60}>
                      {typeData.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-col gap-1.5 flex-1">
                  {typeData.slice(0, 6).map((item, i) => (
                    <div key={item.name} className="flex items-center gap-2 text-xs">
                      <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                      <span className="text-gray-600 truncate">{item.name}</span>
                      <span className="ml-auto font-medium text-gray-800">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Scan history bar */}
            <div className="bg-white rounded-2xl p-4 border border-gray-100 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Recent Scans — Device Count</h3>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={[...scanLogs].reverse().slice(-10)}>
                  <XAxis dataKey="scan_number" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip
                    formatter={(val) => [val, 'Devices']}
                    labelFormatter={(n) => `Scan #${n}`}
                  />
                  <Bar dataKey="total_devices" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Search + Device table */}
        <div className="space-y-3">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search by IP, hostname, MAC, vendor..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-blue-400 bg-white"
            />
          </div>

          {loading && (
            <div className="text-center py-12 text-gray-400">
              <RefreshCw size={24} className="mx-auto mb-3 animate-spin" />
              <p>Loading devices...</p>
            </div>
          )}

          {!loading && (
            <DeviceTable
              devices={filteredDevices}
              onSelect={setSelectedDevice}
            />
          )}
        </div>

        {lastScanTime && (
          <p className="text-xs text-gray-400 text-center">
            Last scan: {lastScanTime.toLocaleTimeString()}
          </p>
        )}
      </main>

      {/* Device detail panel */}
      {selectedDevice && (
        <DeviceCard
          device={selectedDevice}
          onClose={() => setSelectedDevice(null)}
          onUpdate={(updated) => {
            applyEvent('device_updated', updated);
            setSelectedDevice(updated);
          }}
          onDeepScan={agents.length ? handleDeepScan : null}
        />
      )}
    </div>
  );
}
