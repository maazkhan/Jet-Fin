import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../api/client';

function ReconciliationView({ tenant, dateRange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!tenant) return;
    setLoading(true);
    setError(null);
    // Note: reconciliation shows all audits (not filtered by ingestion date range)
    // because audits are timestamped when recorded, not when data occurred
    analyticsAPI
      .get(`/api/v1/tenants/${tenant}/reconciliation`)
      .then((r) => setData(r.data))
      .catch(() => setError('Failed to load reconciliation data'))
      .finally(() => setLoading(false));
  }, [tenant]);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (error)   return <div className="text-center py-12 text-red-500">{error}</div>;
  if (!data)   return null;

  const summary = data.summary || {};
  const audits = data.audits || [];

  const rawToCost = parseFloat(summary.total_raw_cost_usd || 0);
  const normCost = parseFloat(summary.total_normalized_cost_usd || 0);
  const allocCost = parseFloat(summary.total_allocated_cost_usd || 0);
  const unallocCost = parseFloat(summary.total_unallocated_cost_usd || 0);

  return (
    <div className="space-y-6">
      {/* Data Flow Diagram */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-bold text-gray-800 mb-6">📊 Data Flow & Reconciliation</h2>

        <div className="flex items-center justify-between mb-8">
          {/* Raw */}
          <div className="bg-gray-50 rounded-lg p-4 flex-1 text-center">
            <p className="text-sm text-gray-500 font-medium">Raw Events</p>
            <p className="text-3xl font-bold text-gray-800">{summary.total_raw_records}</p>
            <p className="text-sm text-gray-600 mt-1">${rawToCost.toFixed(2)}</p>
          </div>

          {/* Arrow + delta */}
          <div className="mx-4 text-center flex-shrink-0">
            <p className="text-xs text-gray-500 mb-2">Normalization</p>
            <div className="text-2xl text-gray-400">→</div>
            <p className="text-xs text-gray-500 mt-2">
              Δ ${parseFloat(summary.raw_to_normalized_delta_usd || 0).toFixed(2)}
            </p>
          </div>

          {/* Normalized */}
          <div className="bg-blue-50 rounded-lg p-4 flex-1 text-center border border-blue-200">
            <p className="text-sm text-blue-600 font-medium">Normalized Events</p>
            <p className="text-3xl font-bold text-blue-800">{summary.total_normalized_records}</p>
            <p className="text-sm text-blue-600 mt-1">${normCost.toFixed(2)}</p>
          </div>

          {/* Arrow + split */}
          <div className="mx-4 text-center flex-shrink-0">
            <p className="text-xs text-gray-500 mb-2">Allocation</p>
            <div className="text-2xl text-gray-400">→</div>
            <p className="text-xs text-gray-500 mt-2">
              {parseFloat(summary.overall_allocation_rate_percent || 0).toFixed(1)}% allocated
            </p>
          </div>

          {/* Split: Allocated vs Unallocated */}
          <div className="flex gap-2 flex-1">
            <div className="bg-green-50 rounded-lg p-4 flex-1 text-center border border-green-200">
              <p className="text-sm text-green-600 font-medium">Allocated</p>
              <p className="text-2xl font-bold text-green-800">{summary.total_allocated_records}</p>
              <p className="text-sm text-green-600 mt-1">${allocCost.toFixed(2)}</p>
            </div>
            <div className="bg-yellow-50 rounded-lg p-4 flex-1 text-center border border-yellow-200">
              <p className="text-sm text-yellow-600 font-medium">Unallocated</p>
              <p className="text-2xl font-bold text-yellow-800">
                {summary.total_normalized_records - summary.total_allocated_records}
              </p>
              <p className="text-sm text-yellow-600 mt-1">${unallocCost.toFixed(2)}</p>
            </div>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-4 gap-4 pt-6 border-t">
          <div>
            <p className="text-xs text-gray-500 font-medium">Raw → Normalized Delta</p>
            <p className={`text-lg font-bold ${Math.abs(parseFloat(summary.raw_to_normalized_delta_usd || 0)) < 0.01 ? 'text-green-600' : 'text-red-600'}`}>
              ${parseFloat(summary.raw_to_normalized_delta_usd || 0).toFixed(2)}
            </p>
            {Math.abs(parseFloat(summary.raw_to_normalized_delta_usd || 0)) < 0.01 && (
              <p className="text-xs text-green-600">✓ No data loss</p>
            )}
          </div>
          <div>
            <p className="text-xs text-gray-500 font-medium">Allocation Rate</p>
            <p className="text-lg font-bold text-blue-600">{parseFloat(summary.overall_allocation_rate_percent || 0).toFixed(1)}%</p>
            <p className="text-xs text-gray-500">{summary.total_allocated_records} of {summary.total_normalized_records}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 font-medium">Unallocated Cost</p>
            <p className="text-lg font-bold text-yellow-600">${unallocCost.toFixed(2)}</p>
            <p className="text-xs text-gray-500">Needs review</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 font-medium">Audit Batches</p>
            <p className="text-lg font-bold text-gray-800">{summary.audit_batches_count}</p>
            <p className="text-xs text-gray-500">ingestion runs</p>
          </div>
        </div>
      </div>

      {/* Detailed Audit Table */}
      {audits.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold text-gray-800">Detailed Audits</h3>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-6 py-3 text-left text-gray-600 font-medium">Batch ID</th>
                  <th className="px-6 py-3 text-left text-gray-600 font-medium">Source</th>
                  <th className="px-6 py-3 text-right text-gray-600 font-medium">Raw Count</th>
                  <th className="px-6 py-3 text-right text-gray-600 font-medium">Raw Cost</th>
                  <th className="px-6 py-3 text-right text-gray-600 font-medium">Norm Count</th>
                  <th className="px-6 py-3 text-right text-gray-600 font-medium">Alloc %</th>
                  <th className="px-6 py-3 text-right text-gray-600 font-medium">Alloc Cost</th>
                  <th className="px-6 py-3 text-right text-gray-600 font-medium">Unalloc Cost</th>
                  <th className="px-6 py-3 text-left text-gray-600 font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {audits.map((audit, idx) => {
                  const allocPct = audit.allocated_total_cost > 0 ? (audit.allocated_total_cost / (audit.allocated_total_cost + audit.unallocated_total_cost) * 100).toFixed(1) : 0;
                  return (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-6 py-3 font-mono text-xs text-gray-600">{audit.batch_id.substring(0, 8)}</td>
                      <td className="px-6 py-3">{audit.source_type}</td>
                      <td className="px-6 py-3 text-right font-mono">{audit.raw_record_count}</td>
                      <td className="px-6 py-3 text-right font-mono">${parseFloat(audit.raw_total_cost).toFixed(2)}</td>
                      <td className="px-6 py-3 text-right font-mono">{audit.normalized_record_count}</td>
                      <td className="px-6 py-3 text-right font-mono text-green-600">{allocPct}%</td>
                      <td className="px-6 py-3 text-right font-mono text-green-600">${parseFloat(audit.allocated_total_cost).toFixed(2)}</td>
                      <td className="px-6 py-3 text-right font-mono text-yellow-600">${parseFloat(audit.unallocated_total_cost).toFixed(2)}</td>
                      <td className="px-6 py-3 text-xs text-gray-500">{new Date(audit.created_at).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* No data state */}
      {audits.length === 0 && (
        <div className="text-center py-12 bg-white rounded-lg">
          <p className="text-lg text-gray-500">📭 No reconciliation audits in this period</p>
          <p className="text-sm text-gray-400 mt-2">Upload data to generate audit records</p>
        </div>
      )}

      {/* Info box */}
      <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
        <p className="text-sm text-blue-900">
          <strong>How to read this:</strong> The reconciliation view tracks data integrity across the pipeline.
          Raw events are uploaded; normalized events remove duplicates/malformed data; allocation assigns costs to business entities.
          The delta should always be ≤0 (no data loss). Unallocated costs are those matching no allocation rules.
        </p>
      </div>
    </div>
  );
}

export default ReconciliationView;
