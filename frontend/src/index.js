import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import './utils/fetchAuthShim';
import App from './App';

const existingToken = localStorage.getItem('auth_token');
if (existingToken && window?.electronAPI?.setAuthToken) {
  window.electronAPI.setAuthToken(existingToken);
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
