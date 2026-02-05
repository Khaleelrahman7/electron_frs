import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import './utils/fetchAuthShim'; // Initialize auth interceptors
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
