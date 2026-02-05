import axios from 'axios';
import useAuthStore from '../store/authStore';

// Global fetch shim to inject auth token
(function() {
  const originalFetch = window.fetch;
  
  window.fetch = async function(...args) {
    const [url, options = {}] = args;
    
    // Get auth token from localStorage (or store)
    const token = localStorage.getItem('auth_token');
    
    if (token && url.includes('/api/')) {
      // Clone options to avoid modifying the original
      const modifiedOptions = {
        ...options,
        headers: {
          ...options.headers,
          'Authorization': `Bearer ${token}`,
        },
      };
      
      return originalFetch(url, modifiedOptions);
    }
    
    return originalFetch(...args);
  };
})();

// Axios interceptor for auth token injection
// We modify the default instance which is used when importing 'axios'
axios.interceptors.request.use(
  function(config) {
    const token = localStorage.getItem('auth_token');
    if (token && config.url && config.url.includes('/api/')) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  function(error) {
    return Promise.reject(error);
  }
);

// Response interceptor to handle auth errors
axios.interceptors.response.use(
  function(response) {
    return response;
  },
  function(error) {
    if (error.response && error.response.status === 401) {
      // Clear invalid token and logout via store
      console.warn('Authentication token invalid, logging out...');
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  }
);

// Export helper functions for manual API calls
export const apiRequest = async (url, options = {}) => {
  const token = localStorage.getItem('auth_token');
  
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  
  if (token && url.includes('/api/')) {
    headers.Authorization = `Bearer ${token}`;
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
};

export const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};