import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../api/client';

function CostSummary({ tenant, dateRange }) {
  const [summary, setSummary]     = useState(null);
  const [drivers, setDrivers]     = useState(null);
  const [loading, setLoading]     = useState(false);

  useEffect(() => {
    if (!tenant) return;
    setLoading(true);
    Promise.all([
      analyticsAPI.get(
        `/api/v1/tenants/${tenant}/cost-summary` +
        `?from_date=${dateRange.from}&to_date=${dateRange.to}`
      ),
      analyticsAPI.get(
        `/api/v1/tenants/${tenant}/top-drivers` +
        `?from_date=${dateRange.from}&to_date=${dateRange.to}&limit=8`
      ),
    ])
      .then(([s, d]) => { setSummary(s.data); setDrivers(d.data); })
      .catch((e) => console.error('Failed to load overview:', e))
      .finally(() => setLoading(false));
  }, [tenant, dateRange]);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (!summary) return <div className="text-center py-12 text-gray-400">No data available</div>;

  const total       = summary.total_cost_usd || 0;
  const allocated   = summary.allocated_cost_usd || 0;
  const unallocated = summary.unallocated_cost_usd || 0;
  const allocPct    = total > 0 ? ((allocated / total) * 100).toFixed(1) : 0;

  // Unique dates for daily average
  const uniqueDates = [...new Set((summary.items || []).map((i) => i.date))];
  const dayCount    = uniqueDates.length || 1;
  const dailyAvg    = total / dayCount;

  // Daily trend — sum cost_usd per date across all services
  const dailyMap = {};
  (summary.items || []).forEach((item) => {
    dailyMap[item.date] = (dailyMap[item.date] || 0) + (item.cost_usd || 0);
  });
  const dailyTrend  = Object.entries(dailyMap).sort(([a], [b]) => a.localeCompare(b));
  const maxDailyCost = Math.max(...dailyTrend.map(([, c]) => Math.abs(c)), 1);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Total Cost"
          value={`$${total.toFixed(2)}`}
          sub={`${dayCount} day${dayCount !== 1 ? 's' : ''}`}
          color="blue"
        />
        <KPICard
          label="Allocated"
          value={`$${allocated.toFixed(2)}`}
          sub={`${allocPct}% of total`}
          color="green"
        />
        <KPICard
          label="Unallocated"
          value={`$${unallocated.toFixed(2)}`}
          sub={`${(100 - allocPct).toFixed(1)}% of total`}
          color="amber"
        />
        <KPICard
          label="Daily Average"
          value={`$${dailyAvg.toFixed(2)}`}
          sub="avg cost / day"
          color="purple"
        />
      </div>

      {/* Allocation progress */}
      <div className="bg-white rounded-lg border p-5">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-semibold text-gray-700">Allocation Coverage</span>
          <span className="text-sm font-bold text-green-600">{allocPct}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-green-400 to-green-600 transition-all"
            style={{ width: `${allocPct}%` }}
          />
        </div>
        <div className="flex justify-between text-xs text-gray-500 mt-1.5">
          <span>Allocated: ${allocated.toFixed(2)}</span>
          <span>Unallocated: ${unallocated.toFixed(2)}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Services (from top-drivers) */}
        {drivers && drivers.top_drivers?.length > 0 && (
          <div className="bg-white rounded-lg border p-5">
            <h3 className="font-semibold text-gray-800 mb-4">Top Services by Spend</h3>
            <div className="space-y-3">
              {drivers.top_drivers.map((d) => (
                <div key={d.rank}>
                  <div className="flex justify-between text-sm mb-1">
                    <div className="flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-blue-100 text-blue-600 text-xs font-bold flex items-center justify-center">
                        {d.rank}
                      </span>
                      <span className="text-gray-700 font-medium truncate max-w-[160px]">{d.service}</span>
                    </div>
                    <span className="text-gray-600 font-semibold whitespace-nowrap">
                      ${d.cost_usd?.toFixed(2)}
                      <span className="text-gray-400 font-normal ml-1">({d.percent_of_total?.toFixed(1)}%)</span>
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full"
                      style={{ width: `${Math.min(d.percent_of_total, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Daily Trend */}
        {dailyTrend.length > 0 && (
          <div className="bg-white rounded-lg border p-5">
            <h3 className="font-semibold text-gray-800 mb-4">Daily Cost Trend</h3>
            <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
              {dailyTrend.slice(-14).map(([d, cost]) => {
                const isCredit = cost < 0;
                const pct = (Math.abs(cost) / maxDailyCost) * 100;
                return (
                  <div key={d} className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 w-20 shrink-0">{d}</span>
                    <div className="flex-1 bg-gray-100 rounded h-5 relative overflow-hidden">
                      <div
                        className={`${isCredit ? 'bg-emerald-400' : 'bg-indigo-500'} h-full rounded transition-all`}
                        style={{ width: `${pct}%` }}
                      />
                      <span className="absolute inset-0 flex items-center justify-end pr-2 text-xs font-semibold text-white drop-shadow">
                        {isCredit ? '-' : ''}${Math.abs(cost).toFixed(0)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Detailed breakdown table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <div className="px-5 py-3 bg-gray-50 border-b">
          <h3 className="font-semibold text-gray-700 text-sm">Cost by Service · Day</h3>
        </div>
        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 sticky top-0">
              <tr>
                <th className="px-4 py-2.5 text-left font-semibold text-gray-600">Date</th>
                <th className="px-4 py-2.5 text-left font-semibold text-gray-600">Service</th>
                <th className="px-4 py-2.5 text-right font-semibold text-gray-600">Total</th>
                <th className="px-4 py-2.5 text-right font-semibold text-gray-600">Allocated</th>
                <th className="px-4 py-2.5 text-right font-semibold text-gray-600">Unallocated</th>
                <th className="px-4 py-2.5 text-right font-semibold text-gray-600">Records</th>
              </tr>
            </thead>
            <tbody>
              {(summary.items || []).map((item, idx) => (
                <tr key={idx} className="border-b hover:bg-gray-50 transition">
                  <td className="px-4 py-2 text-gray-500 text-xs">{item.date}</td>
                  <td className="px-4 py-2 font-medium text-gray-800">{item.service || '—'}</td>
                  <td className={`px-4 py-2 text-right font-semibold ${item.cost_usd < 0 ? 'text-emerald-600' : 'text-gray-900'}`}>
                    ${(item.cost_usd || 0).toFixed(2)}
                  </td>
                  <td className="px-4 py-2 text-right text-green-600">${(item.allocated_cost_usd || 0).toFixed(2)}</td>
                  <td className="px-4 py-2 text-right text-amber-600">${(item.unallocated_cost_usd || 0).toFixed(2)}</td>
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

function KPICard({ label, value, sub, color }) {
  const palette = {
    blue:   'from-blue-50 to-blue-100 border-blue-200 text-blue-600',
    green:  'from-green-50 to-green-100 border-green-200 text-green-600',
    amber:  'from-amber-50 to-amber-100 border-amber-200 text-amber-600',
    purple: 'from-purple-50 to-purple-100 border-purple-200 text-purple-600',
  };
  return (
    <div className={`bg-gradient-to-br ${palette[color]} border rounded-lg p-5`}>
      <p className="text-gray-500 text-xs font-semibold uppercase tracking-wide">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${palette[color].split(' ')[3]}`}>{value}</p>
      <p className="text-xs text-gray-400 mt-1">{sub}</p>
    </div>
  );
}

export default CostSummary;
