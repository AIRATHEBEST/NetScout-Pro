export function PortList({ ports }) {
  if (!ports?.length) {
    return (
      <div className="text-center py-8 text-gray-400 text-sm">
        No open ports found
      </div>
    );
  }

  const riskColor = {
    HIGH: 'text-red-600 bg-red-50',
    MEDIUM: 'text-yellow-600 bg-yellow-50',
    LOW: 'text-gray-500 bg-gray-50',
  };

  return (
    <div className="space-y-2">
      {ports.map((p, i) => (
        <div key={i} className="flex items-start gap-3 p-3 rounded-xl border border-gray-100 hover:border-blue-100 transition">
          <div className="min-w-[72px]">
            <span className="font-mono font-bold text-blue-700 text-sm">{p.port}</span>
            <span className="text-gray-400 text-xs">/{p.protocol}</span>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-gray-800 text-sm">{p.service || 'unknown'}</span>
              {p.product && (
                <span className="text-xs text-gray-500">{p.product} {p.version}</span>
              )}
            </div>
            {p.banner && (
              <p className="text-xs text-gray-400 font-mono mt-0.5 truncate">{p.banner}</p>
            )}
            {p.extrainfo && (
              <p className="text-xs text-gray-400 mt-0.5">{p.extrainfo}</p>
            )}
          </div>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${riskColor[p.risk_level] || riskColor.LOW}`}>
            {p.risk_level}
          </span>
        </div>
      ))}
    </div>
  );
}
