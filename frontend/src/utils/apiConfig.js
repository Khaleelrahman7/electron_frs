// Smart API URL detection: defaults to 192.168.1.209, can be overridden
// Priority: 1. Environment variable, 2. 192.168.1.209 (for local dev), 3. Server IP (fallback)
const getApiBaseUrl = () => {
  // If explicitly set via environment variable, use it
  if (process.env.REACT_APP_API_BASE_URL) {
    return process.env.REACT_APP_API_BASE_URL;
  }
  
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

/**
 * Fixes image URLs that might contain localhost, replacing them with the configured API URL.
 * @param {string} url - The image URL to fix
 * @returns {string} - The fixed image URL
 */
export const fixImageUrl = (url) => {
  if (!url) return '';
  if (url.includes('localhost')) {
    // Replaces localhost with the configured API_BASE_URL (default: 192.168.1.209:8005)
    const currentApiUrl = API_BASE_URL.endsWith('/') ? API_BASE_URL.slice(0, -1) : API_BASE_URL;
    return url.replace(/http:\/\/localhost:\d+/, currentApiUrl);
  }
  return url;
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
  fixImageUrl,
  detectBackendUrl
};
