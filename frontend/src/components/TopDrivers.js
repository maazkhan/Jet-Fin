import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../api/client';

function TopDrivers({ tenant, dateRange }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchData();
  }, [tenant, dateRange]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await analyticsAPI.get(
        `/api/v1/tenants/${tenant}/top-drivers?from_date=${dateRange.from}&to_date=${dateRange.to}`
      );
      setData(response.data);
    } catch (error) {
      console.error('Failed to fetch top drivers:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-center py-8">Loading...</div>;
  if (!data) return <div className="text-center py-8">No data available</div>;

  return (
    <div className="space-y-6">
      <div className="bg-blue-50 p-6 rounded-lg">
        <p className="text-gray-600 text-sm">Total Cost Period</p>
        <p className="text-3xl font-bold text-blue-600">${data.total_cost_usd?.toFixed(2)}</p>
      </div>

      <div className="space-y-3">
        {data.top_drivers?.map((driver) => (
          <div key={driver.rank} className="bg-white p-4 rounded-lg border">
            <div className="flex items-center justify-between mb-2">
              <span className="font-semibold">{driver.rank}. {driver.service}</span>
              <span className="text-lg font-bold">${driver.cost_usd?.toFixed(2)}</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full"
                style={{ width: `${driver.percent_of_total}%` }}
              />
            </div>
            <p className="text-sm text-gray-600 mt-1">{driver.percent_of_total?.toFixed(1)}% of total</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default TopDrivers;
