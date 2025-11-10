export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://192.168.1.209:8005';

export const getAugmentUrl = () => {
  return API_BASE_URL;
};

export const getApiUrl = (endpoint) => {
  return `${API_BASE_URL}${endpoint}`;
};

export default {
  API_BASE_URL,
  getAugmentUrl,
  getApiUrl
};
