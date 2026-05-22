import React from 'react';
import { format, subDays, subMonths } from 'date-fns';

function Header({ tenant, tenants, loadingTenants, onTenantChange, dateRange, onDateRangeChange }) {
  const DATE_PRESETS = [
    { label: '30D', days: 30 },
    { label: '3M', months: 3 },
    { label: '6M', months: 6 },
    { label: '1Y', months: 12 },
  ];

  const applyPreset = (preset) => {
    const to = format(new Date(), 'yyyy-MM-dd');
    const from = preset.days
      ? format(subDays(new Date(), preset.days), 'yyyy-MM-dd')
      : format(subMonths(new Date(), preset.months), 'yyyy-MM-dd');
    onDateRangeChange({ from, to });
  };

  const getActivePreset = () => {
    const today = format(new Date(), 'yyyy-MM-dd');
    if (dateRange.to !== today) return null;

    for (const preset of DATE_PRESETS) {
      const expectedFrom = preset.days
        ? format(subDays(new Date(), preset.days), 'yyyy-MM-dd')
        : format(subMonths(new Date(), preset.months), 'yyyy-MM-dd');
      if (dateRange.from === expectedFrom) {
        return preset.label;
      }
    }
    return null;
  };

  const activePreset = getActivePreset();

  const handleFromDateChange = (e) => {
    onDateRangeChange({ ...dateRange, from: e.target.value });
  };

  const handleToDateChange = (e) => {
    onDateRangeChange({ ...dateRange, to: e.target.value });
  };

  return (
    <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-40">
      <div className="px-8 py-4">
        <div className="flex items-center justify-between">
          {/* Left: Tenant Selector */}
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label className="text-sm font-semibold text-gray-700">Tenant:</label>
              <select
                value={tenant || ''}
                onChange={(e) => onTenantChange(e.target.value)}
                disabled={loadingTenants}
                className="px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm font-medium bg-white cursor-pointer hover:border-gray-400"
              >
                <option value="">
                  {loadingTenants ? 'Loading...' : 'Select a tenant'}
                </option>
                {tenants.map((t) => (
                  <option key={t.id} value={t.name}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Right: Date Range Controls */}
          <div className="flex items-center gap-4">
            {/* Quick Presets */}
            <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
              {DATE_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  onClick={() => applyPreset(preset)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded transition-all duration-150 ${
                    activePreset === preset.label
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-gray-700 hover:bg-white hover:text-blue-600 hover:shadow-sm'
                  }`}
                  title={`Last ${preset.label}`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Custom Date Inputs */}
            <div className="flex gap-2 items-center">
              <input
                type="date"
                value={dateRange.from}
                onChange={handleFromDateChange}
                className="px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              />
              <span className="text-gray-400 text-sm">→</span>
              <input
                type="date"
                value={dateRange.to}
                onChange={handleToDateChange}
                className="px-3 py-2 border border-gray-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              />
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

export default Header;
