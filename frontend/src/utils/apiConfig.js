// Smart API URL detection: defaults to 192.168.1.209, can be overridden
// Priority: 1. Environment variable, 2. 192.168.1.209 (for local dev), 3. Server IP (fallback)
const getApiBaseUrl = () => {
  // If explicitly set via environment variable, use it
  // if (process.env.REACT_APP_API_BASE_URL) {
  //   return process.env.REACT_APP_API_BASE_URL;
  // }
  
  // Default to 192.168.1.209 for local development
  // Can be overridden by setting REACT_APP_API_BASE_URL=http://192.168.1.209:8005
  return 'http://192.168.1.209:8005';
};

export const API_BASE_URL = getApiBaseUrl();

export const getAugmentUrl = () => {
  return API_BASE_URL;
};

export const getApiUrl = (endpoint) => {
  return `${API_BASE_URL}${endpoint}`;
};

// Helper to detect which backend is available (for auto-detection if needed)
export const detectBackendUrl = async () => {
  const urls = [
    'http://192.168.1.209:8005',
    'http://192.168.1.209:8005'
  ];
  
  for (const url of urls) {
    try {
      const response = await fetch(`${url}/api/status`, { 
        method: 'GET',
        signal: AbortSignal.timeout(2000) // 2 second timeout
      });
      if (response.ok) {
        return url;
      }
    } catch (error) {
      // Try next URL
      continue;
    }
  }
  
  // Return default if none found
  return API_BASE_URL;
};

export default {
  API_BASE_URL,
  getAugmentUrl,
  getApiUrl,
  detectBackendUrl
};
