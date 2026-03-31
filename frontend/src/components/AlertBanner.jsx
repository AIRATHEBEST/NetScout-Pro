import { useState } from 'react';
import { ShieldAlert, X } from 'lucide-react';
import { api } from '../api/client';

export function AlertBanner({ alerts, onAcknowledge }) {
  const unacked = alerts.filter((a) => !a.is_acknowledged);

  if (!unacked.length) return null;

  const critical = unacked.filter((a) => a.severity === 'CRITICAL');
  const high = unacked.filter((a) => a.severity === 'HIGH');
  const topAlert = critical[0] || high[0] || unacked[0];

  const ack = async (id) => {
    try {
      await api.acknowledgeAlert(id);
      onAcknowledge(id);
    } catch (e) {}
  };

  return (
    <div className={`rounded-xl p-4 flex items-start gap-3 ${
      topAlert.severity === 'CRITICAL' ? 'bg-red-50 border border-red-200' :
      topAlert.severity === 'HIGH' ? 'bg-orange-50 border border-orange-200' :
      'bg-yellow-50 border border-yellow-200'
    }`}>
      <ShieldAlert size={18} className={
        topAlert.severity === 'CRITICAL' ? 'text-red-600 mt-0.5' :
        topAlert.severity === 'HIGH' ? 'text-orange-600 mt-0.5' :
        'text-yellow-600 mt-0.5'
      } />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold uppercase ${
            topAlert.severity === 'CRITICAL' ? 'text-red-600' :
            topAlert.severity === 'HIGH' ? 'text-orange-600' : 'text-yellow-600'
          }`}>{topAlert.severity}</span>
          {unacked.length > 1 && (
            <span className="text-xs text-gray-500">+{unacked.length - 1} more alerts</span>
          )}
        </div>
        <p className="text-sm font-medium text-gray-800 mt-0.5">{topAlert.title}</p>
        <p className="text-xs text-gray-600 mt-0.5">{topAlert.device_ip} — {topAlert.description}</p>
      </div>
      <button
        onClick={() => ack(topAlert.id)}
        className="text-gray-400 hover:text-gray-600"
      >
        <X size={16} />
      </button>
    </div>
  );
}
