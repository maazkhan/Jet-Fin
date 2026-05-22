import React, { useState } from 'react';
import CostSummary from './CostSummary';
import AllocationBreakdown from './AllocationBreakdown';
import UnallocatedCosts from './UnallocatedCosts';
import AnomaliesView from './AnomaliesView';
import BudgetForecasting from './BudgetForecasting';
import ReconciliationView from './ReconciliationView';
import CostDetails from './CostDetails';

const TABS = [
  { id: 'summary',         label: 'Overview',           icon: '📊' },
  { id: 'allocation',      label: 'By Team / Project',  icon: '👥' },
  { id: 'anomalies',       label: 'Anomalies',          icon: '⚠️' },
  { id: 'budgets',         label: 'Budget Forecast',    icon: '📈' },
  { id: 'reconciliation',  label: 'Reconciliation',     icon: '✓' },
  { id: 'unallocated',     label: 'Unallocated',        icon: '❌' },
  { id: 'details',         label: 'Details',            icon: '📋' },
];

function Dashboard({ tenant, refreshKey, dateRange }) {
  const [activeTab, setActiveTab] = useState('summary');

  return (
    <div className="h-full flex flex-col">
      {/* Tab Navigation */}
      <div className="bg-white border-b border-gray-200 px-8">
        <div className="flex overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-4 text-sm font-medium whitespace-nowrap border-b-2 transition-all duration-200 flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600 bg-blue-50'
                  : 'border-transparent text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto bg-gray-50">
        <div className="p-8">
          {activeTab === 'summary'         && <CostSummary        tenant={tenant} dateRange={dateRange} />}
          {activeTab === 'allocation'      && <AllocationBreakdown tenant={tenant} dateRange={dateRange} />}
          {activeTab === 'anomalies'       && <AnomaliesView      tenant={tenant} dateRange={dateRange} />}
          {activeTab === 'budgets'         && <BudgetForecasting  tenant={tenant} />}
          {activeTab === 'reconciliation'  && <ReconciliationView  tenant={tenant} dateRange={dateRange} />}
          {activeTab === 'unallocated'     && <UnallocatedCosts   tenant={tenant} dateRange={dateRange} />}
          {activeTab === 'details'         && <CostDetails        tenant={tenant} dateRange={dateRange} />}
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
