import React, { useState, useEffect } from 'react';
import { analyticsAPI } from '../api/client';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

const ALERT_COLORS = {
  'on-track':  { bg: 'bg-green-50',   border: 'border-green-200',   badge: 'bg-green-100 text-green-800',   bar: '#10b981', icon: '✓' },
  'caution':   { bg: 'bg-yellow-50',  border: 'border-yellow-200',  badge: 'bg-yellow-100 text-yellow-800', bar: '#f59e0b', icon: '⚠' },
  'alert':     { bg: 'bg-orange-50',  border: 'border-orange-200',  badge: 'bg-orange-100 text-orange-800', bar: '#f97316', icon: '⚠' },
  'critical':  { bg: 'bg-red-50',     border: 'border-red-200',     badge: 'bg-red-100 text-red-800',       bar: '#ef4444', icon: '✕' },
};

function BudgetCard({ budget }) {
  const colors = ALERT_COLORS[budget.alert_status] || ALERT_COLORS['on-track'];
  const icon = colors.icon;

  const burnPct = Math.min(parseFloat(budget.burn_rate_percent), 100);
  const projectedOverage = parseFloat(budget.projected_overage);
  const isOverBudget = projectedOverage > 0;

  // Forecast chart data (simulate spending trajectory)
  const daysElapsed = budget.days_elapsed;
  const dailyAvg = parseFloat(budget.daily_avg_spend);
  const budget_amt = parseFloat(budget.budget_amount);

  const forecastData = [];
  for (let day = 1; day <= 30; day++) {
    forecastData.push({
      day,
      projected: Math.min(dailyAvg * day, budget_amt * 1.5),
      budget: budget_amt,
      actual: day <= daysElapsed ? dailyAvg * day : null,
    });
  }

  return (
    <div className={`rounded-lg shadow border-l-4 overflow-hidden ${colors.bg} border ${colors.border}`}>
      <div className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-3xl">{icon}</span>
            <div>
              <h3 className="font-bold text-xl">
                {budget.entity_id}
              </h3>
              <p className="text-sm text-gray-500">
                {budget.period_start} to {budget.period_end}
              </p>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-semibold ${colors.badge}`}>
            {budget.alert_status.toUpperCase()}
          </span>
        </div>

        {/* Key metrics grid */}
        <div className="grid grid-cols-5 gap-2 mb-4">
          <div className="bg-white rounded p-2 text-center">
            <p className="text-xs text-gray-500 font-medium">BUDGET</p>
            <p className="text-sm font-bold text-gray-800">${parseFloat(budget.budget_amount).toFixed(0)}</p>
          </div>
          <div className="bg-white rounded p-2 text-center">
            <p className="text-xs text-gray-500 font-medium">SPENT</p>
            <p className="text-sm font-bold text-gray-800">${parseFloat(budget.spent_amount).toFixed(0)}</p>
          </div>
          <div className="bg-white rounded p-2 text-center">
            <p className="text-xs text-gray-500 font-medium">REMAINING</p>
            <p className={`text-sm font-bold ${parseFloat(budget.remaining_amount) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${parseFloat(budget.remaining_amount).toFixed(0)}
            </p>
          </div>
          <div className="bg-white rounded p-2 text-center">
            <p className="text-xs text-gray-500 font-medium">BURN RATE</p>
            <p className="text-sm font-bold text-gray-800">{parseFloat(budget.burn_rate_percent).toFixed(1)}%</p>
          </div>
          <div className="bg-white rounded p-2 text-center">
            <p className="text-xs text-gray-500 font-medium">DAYS LEFT</p>
            <p className="text-sm font-bold text-gray-800">{budget.days_remaining}</p>
          </div>
        </div>

        {/* Burn rate progress bar */}
        <div className="mb-3">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="font-semibold text-gray-700">Burn Rate</span>
            <span className="text-gray-600">{parseFloat(budget.burn_rate_percent).toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
            <div
              className={`h-2 rounded-full transition-all ${
                burnPct >= 100 ? 'bg-red-600' :
                burnPct >= 90 ? 'bg-orange-600' :
                burnPct >= 75 ? 'bg-yellow-500' :
                'bg-green-500'
              }`}
              style={{ width: `${Math.min(burnPct, 100)}%` }}
            />
          </div>
        </div>

        {/* Forecast chart */}
        <div className="bg-white rounded p-4 mb-4">
          <h4 className="font-semibold text-gray-800 mb-3">📈 30-Day Projection</h4>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={forecastData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="day" label={{ value: 'Day of Month', position: 'insideBottomRight', offset: -5 }} />
              <YAxis label={{ value: 'Cost ($)', angle: -90, position: 'insideLeft' }} />
              <Tooltip
                formatter={(value) => value ? `$${value.toFixed(0)}` : 'N/A'}
                contentStyle={{ backgroundColor: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px' }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="projected"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                name="Projected"
              />
              <Line
                type="monotone"
                dataKey="budget"
                stroke="#10b981"
                strokeDasharray="5 5"
                strokeWidth={2}
                dot={false}
                name="Budget"
              />
              <Line
                type="monotone"
                dataKey="actual"
                stroke="#ef4444"
                strokeWidth={2}
                dot={false}
                name="Actual (YTD)"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Forecast details */}
        <div className="grid grid-cols-3 gap-2 text-xs">
          <div className="bg-blue-50 rounded p-2 border border-blue-200">
            <p className="text-xs font-medium text-blue-900">Daily Avg</p>
            <p className="text-sm font-bold text-blue-600">${parseFloat(budget.daily_avg_spend).toFixed(2)}</p>
          </div>
          <div className="bg-purple-50 rounded p-2 border border-purple-200">
            <p className="text-xs font-medium text-purple-900">Proj. EOM</p>
            <p className="text-sm font-bold text-purple-600">${parseFloat(budget.projected_end_of_period_spend).toFixed(0)}</p>
          </div>
          <div className={`rounded p-2 border ${isOverBudget ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`}>
            <p className={`text-xs font-medium ${isOverBudget ? 'text-red-900' : 'text-green-900'}`}>
              {isOverBudget ? 'Overage' : 'Savings'}
            </p>
            <p className={`text-sm font-bold ${isOverBudget ? 'text-red-600' : 'text-green-600'}`}>
              ${Math.abs(projectedOverage).toFixed(0)}
            </p>
          </div>
        </div>

        {/* Warning if over budget */}
        {isOverBudget && (
          <div className="bg-red-50 border border-red-300 rounded p-4 flex items-start gap-3">
            <span className="text-2xl">⚠️</span>
            <div>
              <p className="font-semibold text-red-900">Budget Alert</p>
              <p className="text-sm text-red-800 mt-1">
                At current pace, you will exceed budget by ${projectedOverage.toFixed(0)} by month-end.
                Consider reviewing spending or adjusting budget.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function BudgetForecasting({ tenant }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedTeams, setSelectedTeams] = useState(new Set());
  const [sortBy, setSortBy] = useState('burn_rate'); // burn_rate, budget, spend

  useEffect(() => {
    if (!tenant) return;
    setLoading(true);
    setError(null);
    analyticsAPI
      .get(`/api/v1/tenants/${tenant}/budgets`)
      .then((r) => setData(r.data))
      .catch(() => setError('Failed to load budgets'))
      .finally(() => setLoading(false));
  }, [tenant]);

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;
  if (error)   return <div className="text-center py-12 text-red-500">{error}</div>;

  const budgets = data?.items || [];

  // Team selection and filtering
  const teams = [...new Set(budgets.map(b => b.entity_id))];
  const displayedBudgets = budgets.filter(b =>
    selectedTeams.size === 0 || selectedTeams.has(b.entity_id)
  );

  // Sort
  const sorted = [...displayedBudgets].sort((a, b) => {
    if (sortBy === 'burn_rate') return parseFloat(b.burn_rate_percent) - parseFloat(a.burn_rate_percent);
    if (sortBy === 'budget') return parseFloat(b.budget_amount) - parseFloat(a.budget_amount);
    if (sortBy === 'spend') return parseFloat(b.spent_amount) - parseFloat(a.spent_amount);
    return 0;
  });

  // Summary stats
  const totalBudget = budgets.reduce((s, b) => s + parseFloat(b.budget_amount), 0);
  const totalSpent = budgets.reduce((s, b) => s + parseFloat(b.spent_amount), 0);
  const avgBurnRate = budgets.length > 0 ? budgets.reduce((s, b) => s + parseFloat(b.burn_rate_percent), 0) / budgets.length : 0;

  const criticalCount = budgets.filter(b => b.alert_status === 'critical').length;

  // Chart data for comparison - use displayed budgets (respects team filter)
  const comparisonData = displayedBudgets.map(b => ({
    name: b.entity_id,
    budget: parseFloat(b.budget_amount),
    spent: parseFloat(b.spent_amount),
    projected: parseFloat(b.projected_end_of_period_spend),
  }));

  return (
    <div className="space-y-6">
      {/* Summary KPIs */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-100">
        <h2 className="text-2xl font-bold text-blue-900 mb-4">💰 Budget Forecast Summary</h2>
        <div className="grid grid-cols-5 gap-4">
          <div>
            <p className="text-sm text-gray-600 font-medium">Total Budget</p>
            <p className="text-3xl font-bold text-blue-600">${totalBudget.toFixed(0)}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 font-medium">Total Spent</p>
            <p className="text-3xl font-bold text-gray-800">${totalSpent.toFixed(0)}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 font-medium">Avg Burn Rate</p>
            <p className="text-3xl font-bold text-orange-600">{avgBurnRate.toFixed(1)}%</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 font-medium">Critical Alerts</p>
            <p className="text-3xl font-bold text-red-600">{criticalCount}</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 font-medium">Teams</p>
            <p className="text-3xl font-bold text-gray-800">{teams.length}</p>
          </div>
        </div>
      </div>

      {/* Charts section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="font-bold text-lg mb-4 text-gray-800">Budget vs Actual Spend</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={comparisonData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip formatter={(value) => `$${value.toFixed(0)}`} />
            <Legend />
            <Bar dataKey="budget" fill="#10b981" name="Budget" />
            <Bar dataKey="spent" fill="#3b82f6" name="Spent" />
            <Bar dataKey="projected" fill="#f59e0b" name="Projected" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Team filter and sort */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex gap-6 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Filter by Team</label>
            <select
              value={selectedTeams.size === 0 ? 'all' : Array.from(selectedTeams)[0] || 'all'}
              onChange={(e) => {
                if (e.target.value === 'all') {
                  setSelectedTeams(new Set());
                } else {
                  setSelectedTeams(new Set([e.target.value]));
                }
              }}
              className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-gray-700 hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Teams</option>
              {teams.map(team => (
                <option key={team} value={team}>{team}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Sort By</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg bg-white text-gray-700 hover:border-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="burn_rate">Burn Rate</option>
              <option value="budget">Budget Amount</option>
              <option value="spend">Spend Amount</option>
            </select>
          </div>
        </div>
      </div>

      {/* Budget cards */}
      {sorted.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg">
          <p className="text-lg text-gray-500">📋 No teams match selected filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-6">
          {sorted.map((budget, idx) => (
            <BudgetCard key={idx} budget={budget} />
          ))}
        </div>
      )}

      {/* Info box */}
      {budgets.length > 0 && (
        <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
          <p className="text-sm text-blue-900">
            <strong>How budgets are calculated:</strong> Budgets are auto-generated from your historical spending patterns.
            Daily average = total historical spend ÷ days with data. Monthly budget = (daily avg × 30) × 1.2 (20% safety buffer).
            Use filters to focus on specific teams, and sort by burn rate to prioritize high-spend areas.
          </p>
        </div>
      )}
    </div>
  );
}

export default BudgetForecasting;
