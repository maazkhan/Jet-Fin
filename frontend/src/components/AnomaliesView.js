import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../api/client';

const SCOPE_COLORS = {
  daily:   { badge: 'bg-red-100 text-red-700',       icon: '📊' },
  service: { badge: 'bg-yellow-100 text-yellow-700', icon: '⚙️' },
  project: { badge: 'bg-purple-100 text-purple-700', icon: '📁' },
};

function AnomalyCard({ anomaly }) {
  const colors = SCOPE_COLORS[anomaly.scope_type] || SCOPE_COLORS.daily;
  const isSpike = anomaly.variance_percent > 0;
  const icon = colors.icon;

  return (
    <div className="bg-white rounded-lg shadow p-6 border-l-4 border-red-500">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{icon}</span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-lg">
                {anomaly.scope_type === 'daily'
                  ? 'Overall Spend Anomaly'
                  : `${anomaly.scope_type.charAt(0).toUpperCase() + anomaly.scope_type.slice(1)}: ${anomaly.scope_id}`}
              </h3>
              <span className={`px-2 py-1 rounded text-xs font-medium ${colors.badge}`}>
                {anomaly.scope_type}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-1">{anomaly.date}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-500">Confidence</p>
          <p className={`text-lg font-bold ${
            anomaly.confidence >= 3 ? 'text-red-600' : 'text-orange-600'
          }`}>
            {parseFloat(anomaly.confidence).toFixed(2)}σ
          </p>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-gray-50 rounded p-3">
          <p className="text-xs text-gray-500 font-medium">BASELINE</p>
          <p className="text-lg font-semibold text-gray-800">${parseFloat(anomaly.baseline_cost).toFixed(2)}</p>
        </div>
        <div className="bg-gray-50 rounded p-3">
          <p className="text-xs text-gray-500 font-medium">ACTUAL</p>
          <p className="text-lg font-semibold text-gray-800">${parseFloat(anomaly.actual_cost).toFixed(2)}</p>
        </div>
        <div className={`rounded p-3 ${isSpike ? 'bg-red-50' : 'bg-green-50'}`}>
          <p className="text-xs font-medium" style={{color: isSpike ? '#991b1b' : '#166534'}}>
            {isSpike ? '↑ SPIKE' : '↓ DIP'}
          </p>
          <p className={`text-lg font-semibold ${isSpike ? 'text-red-600' : 'text-green-600'}`}>
            {isSpike ? '+' : ''}{parseFloat(anomaly.variance_percent).toFixed(1)}%
          </p>
        </div>
      </div>

      <div className="bg-blue-50 rounded p-4 border border-blue-200">
        <p className="text-sm text-blue-900">{anomaly.explanation}</p>
      </div>

      {anomaly.top_drivers && anomaly.top_drivers.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-gray-600 mb-2">TOP DRIVERS</p>
          <div className="space-y-2">
            {anomaly.top_drivers.map((driver, idx) => (
              <div key={idx} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-gray-400"></span>
                  <span className="text-gray-700">{driver.name}</span>
                </div>
                <div className="text-right">
                  <p className="font-medium text-gray-800">${driver.cost.toFixed(2)}</p>
                  <p className="text-xs text-gray-500">{driver.records} records</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AnomaliesView({ tenant, dateRange }) {
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    if (!tenant) return;
    setLoading(true);
    setError(null);
    analyticsAPI
      .get(
        `/api/v1/tenants/${tenant}/anomalies?from_date=${dateRange.from}&to_date=${dateRange.to}`
      )
      .then((r) => {
        const items = r.data.items || [];
        setData(items);
      })
      .catch(() => setError('Failed to load anomalies'))
      .finally(() => setLoading(false));
  }, [tenant, dateRange]);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (error)   return <div className="text-center py-12 text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="bg-gradient-to-r from-red-50 to-orange-50 rounded-lg p-6 border border-red-100">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600 font-medium">Anomalies Detected</p>
            <p className="text-4xl font-bold text-red-600 mt-1">{data.length}</p>
          </div>
          <div className="text-right">
            <p className="text-sm text-gray-600 font-medium">Period</p>
            <p className="text-lg text-gray-800 mt-1">
              {dateRange.from} to {dateRange.to}
            </p>
          </div>
        </div>
      </div>

      {/* No data state */}
      {data.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg">
          <p className="text-lg text-gray-500">✓ No anomalies detected in this period</p>
          <p className="text-sm text-gray-400 mt-2">Your spend patterns are normal</p>
        </div>
      )}

      {/* Anomaly cards */}
      <div className="grid grid-cols-1 gap-6">
        {data.map((anomaly, idx) => (
          <AnomalyCard key={idx} anomaly={anomaly} />
        ))}
      </div>

      {/* Info box */}
      {data.length > 0 && (
        <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
          <p className="text-sm text-blue-900">
            <strong>How to read this:</strong> Anomalies are detected using Z-score analysis against a 7-day trailing baseline.
            Confidence score (σ) indicates statistical significance — higher values mean stronger deviation from normal patterns.
          </p>
        </div>
      )}
    </div>
  );
}

export default AnomaliesView;
