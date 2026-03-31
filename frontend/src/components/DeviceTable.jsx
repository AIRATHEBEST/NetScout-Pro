import { useState } from 'react';
import { Wifi, WifiOff, Shield, ShieldAlert, ChevronRight, Cpu, Smartphone, Server, Printer, Router, Monitor, HelpCircle } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const DEVICE_ICONS = {
  windows_pc: Monitor,
  linux_pc: Monitor,
  mac: Monitor,
  server: Server,
  mobile: Smartphone,
  apple_device: Smartphone,
  router: Router,
  printer: Printer,
  smart_device: Cpu,
  smart_home: Cpu,
  chromecast: Monitor,
  camera: Monitor,
  workstation: Monitor,
  unknown: HelpCircle,
};

function DeviceIcon({ type }) {
  const Icon = DEVICE_ICONS[type] || HelpCircle;
  return <Icon size={18} className="text-gray-400" />;
}

function RiskBadge({ vulnerabilities = [] }) {
  if (!vulnerabilities.length) return null;
  const hasCritical = vulnerabilities.some((v) => v.severity === 'CRITICAL');
  const hasHigh = vulnerabilities.some((v) => v.severity === 'HIGH');
  const color = hasCritical ? 'bg-red-100 text-red-700' : hasHigh ? 'bg-orange-100 text-orange-700' : 'bg-yellow-100 text-yellow-700';
  const label = hasCritical ? 'CRITICAL' : hasHigh ? 'HIGH' : 'MEDIUM';
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {label}
    </span>
  );
}

export function DeviceTable({ devices, onSelect }) {
  const [sort, setSort] = useState({ field: 'last_seen', dir: 'desc' });
  const [filter, setFilter] = useState('all'); // all | online | offline

  const sorted = [...devices]
    .filter((d) => {
      if (filter === 'online') return d.is_online;
      if (filter === 'offline') return !d.is_online;
      return true;
    })
    .sort((a, b) => {
      const dir = sort.dir === 'asc' ? 1 : -1;
      if (sort.field === 'last_seen') {
        return dir * (new Date(a.last_seen) - new Date(b.last_seen));
      }
      return dir * String(a[sort.field] || '').localeCompare(String(b[sort.field] || ''));
    });

  const toggleSort = (field) => {
    setSort((s) => ({ field, dir: s.field === field && s.dir === 'asc' ? 'desc' : 'asc' }));
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      {/* Filters */}
      <div className="px-4 py-3 border-b border-gray-100 flex gap-2">
        {['all', 'online', 'offline'].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-sm font-medium transition ${
              filter === f ? 'bg-blue-600 text-white' : 'text-gray-500 hover:bg-gray-100'
            }`}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
        <span className="ml-auto text-sm text-gray-400">{sorted.length} devices</span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wide">
            <tr>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left cursor-pointer hover:text-gray-900" onClick={() => toggleSort('ip')}>IP</th>
              <th className="px-4 py-3 text-left cursor-pointer hover:text-gray-900" onClick={() => toggleSort('hostname')}>Hostname</th>
              <th className="px-4 py-3 text-left">MAC / Vendor</th>
              <th className="px-4 py-3 text-left">Type</th>
              <th className="px-4 py-3 text-left">OS</th>
              <th className="px-4 py-3 text-left">Ports</th>
              <th className="px-4 py-3 text-left">Risk</th>
              <th className="px-4 py-3 text-left cursor-pointer hover:text-gray-900" onClick={() => toggleSort('last_seen')}>Last Seen</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {sorted.map((device) => (
              <tr
                key={device.id || device.ip}
                className="hover:bg-blue-50/40 cursor-pointer transition"
                onClick={() => onSelect(device)}
              >
                <td className="px-4 py-3">
                  {device.is_online
                    ? <Wifi size={16} className="text-green-500" />
                    : <WifiOff size={16} className="text-gray-300" />}
                </td>
                <td className="px-4 py-3 font-mono font-medium text-gray-800">{device.ip}</td>
                <td className="px-4 py-3 text-gray-600 max-w-[180px] truncate">
                  {device.custom_name || device.hostname || device.mdns_name || '—'}
                </td>
                <td className="px-4 py-3">
                  <div className="font-mono text-xs text-gray-500">{device.mac}</div>
                  <div className="text-xs text-gray-400 truncate max-w-[140px]">{device.vendor || '—'}</div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <DeviceIcon type={device.device_type} />
                    <span className="text-gray-600 text-xs">{device.device_type || 'unknown'}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 max-w-[120px] truncate">
                  {device.os_info?.name || '—'}
                </td>
                <td className="px-4 py-3">
                  {device.ports?.length > 0
                    ? <span className="bg-blue-100 text-blue-700 text-xs font-medium px-2 py-0.5 rounded-full">
                        {device.ports.length} open
                      </span>
                    : <span className="text-gray-300 text-xs">—</span>}
                </td>
                <td className="px-4 py-3">
                  <RiskBadge vulnerabilities={device.vulnerabilities} />
                </td>
                <td className="px-4 py-3 text-xs text-gray-400">
                  {device.last_seen
                    ? formatDistanceToNow(new Date(device.last_seen), { addSuffix: true })
                    : '—'}
                </td>
                <td className="px-4 py-3">
                  <ChevronRight size={14} className="text-gray-300" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {sorted.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <Wifi size={32} className="mx-auto mb-3 opacity-30" />
            <p>No devices found. Start an agent scan to discover your network.</p>
          </div>
        )}
      </div>
    </div>
  );
}
