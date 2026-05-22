import React from 'react';
import FileUpload from './FileUpload';

function IngestPage({ onUploadSuccess }) {
  return (
    <div className="p-8 flex flex-col items-center">
      <div className="max-w-2xl w-full">
        {/* Header */}
        <div className="mb-6 text-center">
          <h1 className="text-3xl font-bold text-gray-900">Ingest Billing Data</h1>
          <p className="text-gray-600 mt-2">
            Upload cost and usage data from AWS, Azure, or your internal AI services
          </p>
        </div>

        {/* Upload Card */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <FileUpload onUploadSuccess={onUploadSuccess} isFullPage={true} />
        </div>

        {/* Info Section */}
        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-blue-50 rounded-lg p-6 border border-blue-200">
            <div className="text-2xl mb-3">📋</div>
            <h3 className="font-semibold text-blue-900 mb-2">Supported Formats</h3>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• AWS CUR (CSV)</li>
              <li>• Azure Cost Export (CSV)</li>
              <li>• AI Events (JSONL)</li>
            </ul>
          </div>

          <div className="bg-green-50 rounded-lg p-6 border border-green-200">
            <div className="text-2xl mb-3">⚡</div>
            <h3 className="font-semibold text-green-900 mb-2">Features</h3>
            <ul className="text-sm text-green-800 space-y-1">
              <li>• Automatic deduplication</li>
              <li>• Multi-tenant support</li>
              <li>• Late-arriving tracking</li>
            </ul>
          </div>

          <div className="bg-purple-50 rounded-lg p-6 border border-purple-200">
            <div className="text-2xl mb-3">✓</div>
            <h3 className="font-semibold text-purple-900 mb-2">What Happens Next</h3>
            <ul className="text-sm text-purple-800 space-y-1">
              <li>• Data is normalized</li>
              <li>• Costs are allocated</li>
              <li>• Dashboard updates</li>
            </ul>
          </div>
        </div>

        {/* Requirements */}
        <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-5">
          <h3 className="font-semibold text-amber-900 mb-2 text-sm">Requirements</h3>
          <ul className="text-xs text-amber-800 space-y-1">
            <li>• <strong>Tenant ID:</strong> Must be included in data tags or JSONL</li>
            <li>• <strong>Date format:</strong> ISO format (YYYY-MM-DD)</li>
            <li>• <strong>Cost field:</strong> Must be numeric (USD)</li>
            <li>• <strong>File size:</strong> Up to 100MB per upload</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default IngestPage;
