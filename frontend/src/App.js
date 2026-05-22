import React, { useState, useEffect } from 'react';
import './App.css';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './components/Dashboard';
import IngestPage from './components/IngestPage';
import { format, subMonths } from 'date-fns';
import { analyticsAPI } from './api/client';

function App() {
  const [tenant, setTenant] = useState(null);
  const [tenants, setTenants] = useState([]);
  const [loadingTenants, setLoadingTenants] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [dateRange, setDateRange] = useState({
    from: format(subMonths(new Date(), 12), 'yyyy-MM-dd'),
    to: format(new Date(), 'yyyy-MM-dd'),
  });

  useEffect(() => {
    fetchTenants();
  }, [refreshKey]);

  const fetchTenants = async () => {
    setLoadingTenants(true);
    try {
      const response = await analyticsAPI.get('/api/v1/tenants');
      setTenants(response.data.tenants || []);
    } catch (error) {
      console.error('Failed to fetch tenants:', error);
      setTenants([]);
    } finally {
      setLoadingTenants(false);
    }
  };

  const handleUploadSuccess = () => {
    setRefreshKey(refreshKey + 1);
    fetchTenants();
    setCurrentPage('dashboard');
  };

  const handleDateRangeChange = (newDateRange) => {
    setDateRange(newDateRange);
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <Sidebar
        currentPage={currentPage}
        onPageChange={setCurrentPage}
        tenantCount={tenants.length}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <Header
          tenant={tenant}
          tenants={tenants}
          loadingTenants={loadingTenants}
          onTenantChange={setTenant}
          dateRange={dateRange}
          onDateRangeChange={handleDateRangeChange}
        />

        {/* Page Content */}
        <main className="flex-1 overflow-auto">
          {currentPage === 'ingest' ? (
            <IngestPage onUploadSuccess={handleUploadSuccess} />
          ) : (
            tenant ? (
              <Dashboard tenant={tenant} refreshKey={refreshKey} dateRange={dateRange} />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <p className="text-gray-500 text-lg">
                    {loadingTenants ? 'Loading tenants...' : 'Select a tenant to view cost analytics'}
                  </p>
                </div>
              </div>
            )
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
