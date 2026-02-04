// Global fetch shim to inject auth token
(function() {
  const originalFetch = window.fetch;
  
  window.fetch = async function(...args) {
    const [url, options = {}] = args;
    
    // Get auth token from localStorage
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
if (typeof window !== 'undefined' && window.axios) {
  window.axios.interceptors.request.use(
    function(config) {
      const token = localStorage.getItem('auth_token');
      if (token && config.url.includes('/api/')) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    function(error) {
      return Promise.reject(error);
    }
  );

  // Response interceptor to handle auth errors
  window.axios.interceptors.response.use(
    function(response) {
      return response;
    },
    function(error) {
      if (error.response && error.response.status === 401) {
        // Clear invalid token
        localStorage.removeItem('auth_token');
        // You could also redirect to login here if needed
        console.warn('Authentication token invalid, please login again');
      }
      return Promise.reject(error);
    }
  );
}

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