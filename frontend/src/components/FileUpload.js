import React, { useState } from 'react';
import { ingestAPI } from '../api/client';

function FileUpload({ onUploadSuccess, isFullPage = false }) {
  const [file, setFile] = useState(null);
  const [sourceType, setSourceType] = useState('aws');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
    setMessage('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) {
      setMessage('Please select a file');
      setMessageType('error');
      return;
    }

    setLoading(true);
    setMessage('');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await ingestAPI.post(
        `/api/v1/ingest?source_type=${sourceType}`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );

      const tenants = response.data.tenants_processed?.join(', ') || 'unknown';
      const recordCount = response.data.records_ingested;
      const errorCount = response.data.records_with_errors;

      let successMsg = `Successfully ingested ${recordCount} records for: ${tenants}`;
      if (errorCount > 0) {
        successMsg += ` (${errorCount} errors)`;
      }

      setMessage(successMsg);
      setMessageType('success');
      setFile(null);
      onUploadSuccess();
      setTimeout(() => setMessage(''), 5000);
    } catch (error) {
      const errorMsg = error.response?.data?.detail || error.message;
      setMessage(`Error: ${errorMsg}`);
      setMessageType('error');
    } finally {
      setLoading(false);
    }
  };

  if (isFullPage) {
    return (
      <form onSubmit={handleSubmit} className="space-y-6 max-w-xl">
        {/* Source Type Selection */}
        <div>
          <label className="block text-sm font-semibold text-gray-900 mb-3">
            Data Source
          </label>
          <div className="grid grid-cols-1 gap-3">
            {[
              { value: 'aws', label: 'AWS Cost & Usage Report', icon: '☁️' },
              { value: 'azure', label: 'Azure Cost Export', icon: '🔷' },
              { value: 'ai_event', label: 'AI/ML Events', icon: '🤖' }
            ].map((option) => (
              <label
                key={option.value}
                className={`flex items-center gap-3 p-4 border-2 rounded-lg cursor-pointer transition-all ${
                  sourceType === option.value
                    ? 'border-blue-600 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <input
                  type="radio"
                  name="sourceType"
                  value={option.value}
                  checked={sourceType === option.value}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="w-4 h-4"
                />
                <span className="text-lg">{option.icon}</span>
                <span className="font-medium text-gray-900">{option.label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* File Upload */}
        <div>
          <label className="block text-sm font-semibold text-gray-900 mb-3">
            Upload File
          </label>
          <div className="relative">
            <input
              type="file"
              onChange={handleFileChange}
              accept=".csv,.jsonl"
              className="hidden"
              id="file-input"
              disabled={loading}
            />
            <label
              htmlFor="file-input"
              className={`flex flex-col items-center justify-center gap-3 p-8 border-2 border-dashed rounded-lg cursor-pointer transition-all ${
                file
                  ? 'border-green-400 bg-green-50'
                  : 'border-gray-300 hover:border-gray-400 bg-gray-50'
              }`}
            >
              <span className="text-4xl">📁</span>
              <div className="text-center">
                <p className="font-semibold text-gray-900">
                  {file ? file.name : 'Click to select file or drag & drop'}
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  CSV or JSONL format (up to 100MB)
                </p>
              </div>
            </label>
          </div>
        </div>

        {/* Upload Button */}
        <button
          type="submit"
          disabled={loading || !file}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition-colors duration-200"
        >
          {loading ? '⏳ Uploading...' : '📤 Upload & Ingest'}
        </button>

        {/* Status Message */}
        {message && (
          <div
            className={`p-4 rounded-lg ${
              messageType === 'success'
                ? 'bg-green-50 border border-green-200 text-green-800'
                : 'bg-red-50 border border-red-200 text-red-800'
            }`}
          >
            <p className="font-medium">{messageType === 'success' ? '✓' : '✕'} {message}</p>
          </div>
        )}
      </form>
    );
  }

  // Compact version for sidebar (if used elsewhere)
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-lg font-semibold mb-4">Upload Cost Data</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Source Type
          </label>
          <select
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="aws">AWS CUR</option>
            <option value="azure">Azure Cost Export</option>
            <option value="ai_event">AI Events</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            File
          </label>
          <input
            type="file"
            onChange={handleFileChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
            accept=".csv,.jsonl"
          />
          <p className="text-xs text-gray-500 mt-1">Tenant ID will be extracted from your data</p>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-md disabled:opacity-50"
        >
          {loading ? 'Uploading...' : 'Upload'}
        </button>

        {message && (
          <div
            className={`text-sm p-2 rounded ${
              messageType === 'success'
                ? 'bg-green-50 text-green-700'
                : 'bg-red-50 text-red-700'
            }`}
          >
            {message}
          </div>
        )}
      </form>
    </div>
  );
}

export default FileUpload;
