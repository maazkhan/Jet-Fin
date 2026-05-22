import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../api/client';

function UnallocatedCosts({ tenant, dateRange }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!tenant) return;
    setLoading(true);
    analyticsAPI
      .get(
        `/api/v1/tenants/${tenant}/unallocated-cost?from_date=${dateRange.from}&to_date=${dateRange.to}`
      )
      .then((r) => setData(r.data))
      .catch((e) => console.error('Failed to fetch unallocated costs:', e))
      .finally(() => setLoading(false));
  }, [tenant, dateRange]);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (!data)   return <div className="text-center py-12 text-gray-400">No data available</div>;

  const total = data.total_unallocated_cost_usd || 0;

  // Group by service to show top offenders
  const byService = {};
  (data.items || []).forEach((item) => {
    byService[item.service] = (byService[item.service] || 0) + (item.cost_usd || 0);
  });
  const topServices = Object.entries(byService)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5);

  return (
    <div className="space-y-6">
      {/* Header KPI */}
      <div className="bg-gradient-to-br from-amber-50 to-amber-100 border border-amber-200 rounded-lg p-6 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide">Total Unallocated</p>
          <p className="text-4xl font-bold text-amber-600 mt-1">${total.toFixed(2)}</p>
          <p className="text-xs text-gray-400 mt-1">{data.items?.length || 0} service·day combinations</p>
        </div>
        <div className="text-5xl opacity-20">⚠</div>
      </div>

      {/* Top unallocated services */}
      {topServices.length > 0 && (
        <div className="bg-white rounded-lg border p-5">
          <h3 className="font-semibold text-gray-700 mb-4">Top Services with Unallocated Spend</h3>
          <div className="space-y-3">
            {topServices.map(([service, cost]) => {
              const pct = total > 0 ? ((cost / total) * 100) : 0;
              return (
                <div key={service}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 font-medium">{service}</span>
                    <span className="text-amber-600 font-semibold">
                      ${cost.toFixed(2)} <span className="text-gray-400 font-normal">({pct.toFixed(1)}%)</span>
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-amber-400 h-2 rounded-full"
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Detail table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <div className="px-5 py-3 bg-gray-50 border-b">
          <h3 className="font-semibold text-gray-700 text-sm">Unallocated Records</h3>
        </div>
        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 sticky top-0">
              <tr>
                <th className="px-4 py-2.5 text-left font-semibold text-gray-600">Date</th>
                <th className="px-4 py-2.5 text-left font-semibold text-gray-600">Service</th>
                <th className="px-4 py-2.5 text-right font-semibold text-gray-600">Unallocated Cost</th>
                <th className="px-4 py-2.5 text-right font-semibold text-gray-600">Records</th>
              </tr>
            </thead>
            <tbody>
              {(data.items || []).map((item, idx) => (
                <tr key={idx} className="border-b hover:bg-gray-50 transition">
                  <td className="px-4 py-2 text-gray-500 text-xs">{item.date}</td>
                  <td className="px-4 py-2 font-medium text-gray-800">{item.service}</td>
                  <td className="px-4 py-2 text-right font-semibold text-amber-600">
                    ${(item.cost_usd || 0).toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right text-gray-400">{item.record_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default UnallocatedCosts;
