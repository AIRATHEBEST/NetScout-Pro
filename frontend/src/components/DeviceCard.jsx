import { useState } from 'react';
import { X, Shield, ShieldAlert, Tag, Edit2, Check, Globe, Terminal } from 'lucide-react';
import { api } from '../api/client';
import { PortList } from './PortList';

export function DeviceCard({ device, onClose, onUpdate, onDeepScan }) {
  const [editing, setEditing] = useState(false);
  const [customName, setCustomName] = useState(device.custom_name || '');
  const [tags, setTags] = useState((device.tags || []).join(', '));
  const [notes, setNotes] = useState(device.notes || '');
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('info'); // info | ports | vulns

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateDevice(device.id, {
        custom_name: customName,
        tags: tags.split(',').map((t) => t.trim()).filter(Boolean),
        notes,
      });
      onUpdate(updated);
      setEditing(false);
    } catch (e) {
      console.error(e);
    } finally {
      setSaving(false);
    }
  };

  const toggleTrust = async () => {
    try {
      const updated = await api.updateDevice(device.id, { is_trusted: !device.is_trusted });
      onUpdate(updated);
    } catch (e) {
      console.error(e);
    }
  };

  const vulns = device.vulnerabilities || [];
  const criticalCount = vulns.filter((v) => v.severity === 'CRITICAL').length;
  const highCount = vulns.filter((v) => v.severity === 'HIGH').length;

  return (
    <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex items-start justify-end p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className={`w-2.5 h-2.5 rounded-full ${device.is_online ? 'bg-green-500' : 'bg-gray-300'}`} />
              <h2 className="font-semibold text-gray-900 text-lg">
                {device.custom_name || device.hostname || device.ip}
              </h2>
            </div>
            <p className="text-sm text-gray-400 mt-0.5 font-mono">{device.ip} · {device.mac}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1">
            <X size={20} />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100 px-5">
          {['info', 'ports', 'vulns'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-3 py-2 text-sm font-medium border-b-2 transition ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-400 hover:text-gray-600'
              }`}
            >
              {tab === 'vulns' ? `Vulns${vulns.length ? ` (${vulns.length})` : ''}` : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1 p-5">
          {activeTab === 'info' && (
            <div className="space-y-4">
              {/* Device info grid */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  ['Vendor', device.vendor || '—'],
                  ['Device Type', device.device_type || '—'],
                  ['OS', device.os_info?.name || '—'],
                  ['OS Accuracy', device.os_info?.accuracy ? `${device.os_info.accuracy}%` : '—'],
                  ['Discovery', device.discovery_method || '—'],
                  ['Network', device.network_cidr || '—'],
                  ['mDNS Name', device.mdns_name || '—'],
                  ['First Seen', device.first_seen ? new Date(device.first_seen).toLocaleDateString() : '—'],
                ].map(([label, value]) => (
                  <div key={label} className="bg-gray-50 rounded-xl p-3">
                    <div className="text-xs text-gray-400 mb-0.5">{label}</div>
                    <div className="text-sm font-medium text-gray-700 truncate">{value}</div>
                  </div>
                ))}
              </div>

              {/* Trust + Actions */}
              <div className="flex gap-2">
                <button
                  onClick={toggleTrust}
                  className={`flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition ${
                    device.is_trusted
                      ? 'bg-green-100 text-green-700 hover:bg-green-200'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  <Shield size={14} />
                  {device.is_trusted ? 'Trusted' : 'Mark Trusted'}
                </button>
                {onDeepScan && (
                  <button
                    onClick={() => onDeepScan(device.ip)}
                    className="flex items-center gap-2 px-3 py-2 rounded-xl text-sm font-medium bg-blue-50 text-blue-600 hover:bg-blue-100 transition"
                  >
                    <Terminal size={14} />
                    Deep Scan
                  </button>
                )}
              </div>

              {/* Editable metadata */}
              <div className="border border-gray-100 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">Device Notes</span>
                  {!editing
                    ? <button onClick={() => setEditing(true)} className="text-blue-500 hover:text-blue-700"><Edit2 size={14} /></button>
                    : <button onClick={save} disabled={saving} className="text-green-500 hover:text-green-700"><Check size={14} /></button>}
                </div>
                {editing ? (
                  <div className="space-y-2">
                    <input
                      className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
                      placeholder="Custom name"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                    />
                    <input
                      className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
                      placeholder="Tags (comma separated)"
                      value={tags}
                      onChange={(e) => setTags(e.target.value)}
                    />
                    <textarea
                      className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm resize-none"
                      placeholder="Notes..."
                      rows={3}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                ) : (
                  <div className="space-y-1 text-sm text-gray-500">
                    {device.tags?.length > 0 && (
                      <div className="flex gap-1 flex-wrap">
                        {device.tags.map((t) => (
                          <span key={t} className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full text-xs">{t}</span>
                        ))}
                      </div>
                    )}
                    {device.notes && <p className="text-gray-600">{device.notes}</p>}
                    {!device.notes && !device.tags?.length && (
                      <p className="text-gray-300 italic">No notes yet. Click edit to add.</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'ports' && (
            <PortList ports={device.ports || []} />
          )}

          {activeTab === 'vulns' && (
            <div className="space-y-3">
              {vulns.length === 0 && (
                <div className="text-center py-8 text-gray-400">
                  <Shield size={28} className="mx-auto mb-2 text-green-400" />
                  <p>No vulnerability indicators found</p>
                </div>
              )}
              {vulns.map((v, i) => (
                <div
                  key={i}
                  className={`rounded-xl p-4 border ${
                    v.severity === 'CRITICAL' ? 'border-red-200 bg-red-50' :
                    v.severity === 'HIGH' ? 'border-orange-200 bg-orange-50' :
                    'border-yellow-200 bg-yellow-50'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <ShieldAlert size={14} className={
                      v.severity === 'CRITICAL' ? 'text-red-600' :
                      v.severity === 'HIGH' ? 'text-orange-600' : 'text-yellow-600'
                    } />
                    <span className={`text-xs font-bold uppercase ${
                      v.severity === 'CRITICAL' ? 'text-red-600' :
                      v.severity === 'HIGH' ? 'text-orange-600' : 'text-yellow-600'
                    }`}>{v.severity}</span>
                    {v.port && <span className="text-xs text-gray-400">Port {v.port}</span>}
                  </div>
                  <p className="font-medium text-gray-800 text-sm">{v.title}</p>
                  <p className="text-xs text-gray-600 mt-1">{v.description}</p>
                  {v.recommendation && (
                    <p className="text-xs text-blue-600 mt-2 font-medium">→ {v.recommendation}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
