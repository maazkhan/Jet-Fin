import axios from 'axios';

const ANALYTICS_API_URL = process.env.REACT_APP_ANALYTICS_API_URL || 'http://localhost:8000';
const INGEST_API_URL = process.env.REACT_APP_INGEST_API_URL || 'http://localhost:8001';

export const analyticsAPI = axios.create({
  baseURL: ANALYTICS_API_URL,
  timeout: 30000,
});

export const ingestAPI = axios.create({
  baseURL: INGEST_API_URL,
  timeout: 60000,
});
