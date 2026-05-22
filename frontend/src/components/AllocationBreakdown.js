import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../api/client';

const ENTITY_COLORS = {
  team:        { bar: 'bg-blue-500',    badge: 'bg-blue-100 text-blue-700',     header: 'text-blue-700' },
  project:     { bar: 'bg-violet-500',  badge: 'bg-violet-100 text-violet-700', header: 'text-violet-700' },
  cost_center: { bar: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700', header: 'text-emerald-700' },
  env:         { bar: 'bg-orange-400',  badge: 'bg-orange-100 text-orange-700', header: 'text-orange-700' },
};

const ENTITY_LABELS = {
  team:        'Teams',
  project:     'Projects',
  cost_center: 'Cost Centers',
  env:         'Environments',
};

function EntityGroup({ type, entities, total }) {
  const colors = ENTITY_COLORS[type] || ENTITY_COLORS.team;
  const label  = ENTITY_LABELS[type] || type;
  const groupTotal = entities.reduce((s, e) => s + e.cost_usd, 0);
  const isEnv = type === 'env';

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className={`font-semibold text-lg ${colors.header}`}>{label}</h3>
          {isEnv && (
            <p className="text-xs text-gray-400 mt-0.5">all spend by environment tag — not an allocation dimension</p>
          )}
        </div>
        <span className="text-sm text-gray-500">
          ${groupTotal.toFixed(2)} &nbsp;·&nbsp;
          {!isEnv && total > 0 ? ((groupTotal / total) * 100).toFixed(1) + '% of total' : ''}
        </span>
      </div>

      <div className="space-y-3">
        {entities.map((e) => {
          const pct = groupTotal > 0 ? Math.abs((e.cost_usd / groupTotal) * 100) : 0;
          const isCredit = e.cost_usd < 0;
          return (
            <div key={e.entity_id}>
              <div className="flex items-center justify-between text-sm mb-1">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors.badge}`}>
                    {e.entity_id}
                  </span>
                  {isCredit && (
                    <span className="text-xs text-emerald-600 font-medium">credit</span>
                  )}
                </div>
                <span className={`font-semibold ${isCredit ? 'text-emerald-600' : 'text-gray-800'}`}>
                  {isCredit ? '-' : ''}${Math.abs(e.cost_usd).toFixed(2)}
                </span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div
                  className={`${isCredit ? 'bg-emerald-400' : colors.bar} h-2 rounded-full transition-all`}
                  style={{ width: `${Math.min(pct, 100)}%` }}
                />
              </div>
              <div className="text-right text-xs text-gray-400 mt-0.5">
                {pct.toFixed(1)}% &nbsp;·&nbsp; {e.record_count} records
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AllocationBreakdown({ tenant, dateRange }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  useEffect(() => {
    if (!tenant) return;
    setLoading(true);
    setError(null);
    analyticsAPI
      .get(
        `/api/v1/tenants/${tenant}/allocation-breakdown?from_date=${dateRange.from}&to_date=${dateRange.to}`
      )
      .then((r) => setData(r.data))
      .catch(() => setError('Failed to load allocation breakdown'))
      .finally(() => setLoading(false));
  }, [tenant, dateRange]);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (error)   return <div className="text-center py-12 text-red-500">{error}</div>;
  if (!data)   return null;

  const byType = data.by_entity_type || {};
  const total  = data.total_cost_usd || 0;
  const hasData = Object.keys(byType).length > 0;

  // Ordered display: teams, projects, cost centers, environments, then anything else
  const typeOrder = ['team', 'project', 'cost_center', 'env'];
  const orderedTypes = [
    ...typeOrder.filter((t) => byType[t]),
    ...Object.keys(byType).filter((t) => !typeOrder.includes(t)),
  ];

  return (
    <div className="space-y-6">
      {/* Summary bar */}
      <div className="bg-gradient-to-r from-blue-50 to-violet-50 rounded-lg p-6 border border-blue-100">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500 font-medium">Total Cost</p>
            <p className="text-4xl font-bold text-blue-700 mt-1">${total.toFixed(2)}</p>
          </div>
          <div className="flex gap-4 flex-wrap">
            {orderedTypes.map((type) => {
              const colors = ENTITY_COLORS[type] || ENTITY_COLORS.team;
              const label  = ENTITY_LABELS[type] || type;
              const groupTotal = byType[type].reduce((s, e) => s + e.cost_usd, 0);
              return (
                <div key={type} className="text-center">
                  <p className={`text-xs font-semibold uppercase tracking-wide ${colors.header}`}>{label}</p>
                  <p className="text-xl font-bold text-gray-800">${groupTotal.toFixed(0)}</p>
                  <p className="text-xs text-gray-400">
                    {byType[type].length} {byType[type].length === 1 ? 'entity' : 'entities'}
                  </p>
                </div>
              );
            })}
          </div>
        </div>

        {/* Proportional stacked bar */}
        {total > 0 && orderedTypes.length > 0 && (
          <div className="mt-4">
            <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
              {orderedTypes.map((type) => {
                const colors = ENTITY_COLORS[type] || ENTITY_COLORS.team;
                const groupTotal = byType[type].reduce((s, e) => s + e.cost_usd, 0);
                const pct = Math.max((groupTotal / total) * 100, 0);
                return (
                  <div
                    key={type}
                    className={`${colors.bar} transition-all`}
                    style={{ width: `${pct}%` }}
                    title={`${ENTITY_LABELS[type] || type}: $${groupTotal.toFixed(2)}`}
                  />
                );
              })}
            </div>
            <div className="flex gap-4 mt-2 flex-wrap">
              {orderedTypes.map((type) => {
                const colors = ENTITY_COLORS[type] || ENTITY_COLORS.team;
                return (
                  <div key={type} className="flex items-center gap-1 text-xs text-gray-500">
                    <span className={`inline-block w-2 h-2 rounded-full ${colors.bar}`} />
                    {ENTITY_LABELS[type] || type}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {!hasData && (
        <div className="text-center py-12 text-gray-400">
          No allocation data for this period. Upload data and run ingestion to populate.
        </div>
      )}

      {/* One card per entity type */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {orderedTypes.map((type) => (
          <EntityGroup
            key={type}
            type={type}
            entities={byType[type]}
            total={total}
          />
        ))}
      </div>
    </div>
  );
}

export default AllocationBreakdown;
