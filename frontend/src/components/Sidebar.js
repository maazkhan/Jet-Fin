import React from 'react';

function Sidebar({ currentPage, onPageChange, tenantCount }) {
  const menuItems = [
    {
      id: 'dashboard',
      label: 'Dashboard',
      icon: '📊',
      description: 'Cost analytics & insights'
    },
    {
      id: 'ingest',
      label: 'Ingest Data',
      icon: '📤',
      description: 'Upload billing files'
    },
  ];

  return (
    <aside className="w-64 bg-white border-r border-gray-200 shadow-sm flex flex-col">
      {/* Logo / App Name */}
      <div className="px-6 py-6 border-b border-gray-200">
        <h1 className="text-xl font-bold text-gray-900">FinOps</h1>
        <p className="text-xs text-gray-500 mt-1">Cost Intelligence</p>
      </div>

      {/* Navigation Menu */}
      <nav className="flex-1 px-4 py-8 space-y-2">
        {menuItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onPageChange(item.id)}
            className={`w-full text-left px-4 py-3 rounded-lg transition-all duration-200 ${
              currentPage === item.id
                ? 'bg-blue-50 border-l-4 border-blue-600 text-blue-900'
                : 'text-gray-700 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-start gap-3">
              <span className="text-xl mt-1">{item.icon}</span>
              <div className="flex-1">
                <p className="font-medium text-sm">{item.label}</p>
                <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>
              </div>
            </div>
          </button>
        ))}
      </nav>

      {/* Footer Stats */}
      <div className="px-4 py-6 border-t border-gray-200 space-y-3">
        <div className="bg-blue-50 rounded-lg p-3">
          <p className="text-xs text-gray-600 font-medium">Active Tenants</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">{tenantCount}</p>
        </div>
        <p className="text-xs text-gray-500">
          Multi-tenant FinOps platform for AWS, Azure, and AI services
        </p>
      </div>
    </aside>
  );
}

export default Sidebar;
