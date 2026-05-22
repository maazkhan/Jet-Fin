import React, { useState, useEffect, useCallback } from 'react';
import { analyticsAPI } from '../api/client';

function CostDetails({ tenant, dateRange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await analyticsAPI.get(
        `/api/v1/tenants/${tenant}/cost-details?from_date=${dateRange.from}&to_date=${dateRange.to}&limit=${limit}&offset=${offset}`
      );
      setData(response.data);
    } catch (error) {
      console.error('Failed to fetch cost details:', error);
    } finally {
      setLoading(false);
    }
  }, [tenant, dateRange, offset]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) return <div className="text-center py-8">Loading...</div>;
  if (!data) return <div className="text-center py-8">No data available</div>;

  const hasMore = offset + limit < data.total_count;

  return (
    <div className="space-y-6">
      <div className="text-sm text-gray-600">
        Showing {offset + 1} to {Math.min(offset + limit, data.total_count)} of {data.total_count} records
      </div>

      <div className="bg-gray-50 rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-200">
            <tr>
              <th className="px-4 py-2 text-left">Date</th>
              <th className="px-4 py-2 text-left">Service</th>
              <th className="px-4 py-2 text-left">Resource</th>
              <th className="px-4 py-2 text-right">Cost</th>
              <th className="px-4 py-2 text-center">Allocated</th>
            </tr>
          </thead>
          <tbody>
            {data.items?.map((item, idx) => (
              <tr key={idx} className="border-b hover:bg-gray-100">
                <td className="px-4 py-2">{item.event_date}</td>
                <td className="px-4 py-2">{item.service}</td>
                <td className="px-4 py-2 text-xs truncate">{item.resource_id}</td>
                <td className="px-4 py-2 text-right">${item.cost_usd?.toFixed(4)}</td>
                <td className="px-4 py-2 text-center">
                  {item.is_allocated ? (
                    <span className="text-green-600">✓</span>
                  ) : (
                    <span className="text-yellow-600">✗</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between items-center">
        <button
          onClick={() => setOffset(Math.max(0, offset - limit))}
          disabled={offset === 0}
          className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
        >
          Previous
        </button>
        <button
          onClick={() => setOffset(offset + limit)}
          disabled={!hasMore}
          className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}

export default CostDetails;
