import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import DatePicker from 'react-datepicker';
import { format, subDays } from 'date-fns';
import FaceCard from './FaceCard';
import "react-datepicker/dist/react-datepicker.css";
import './FaceEvents.css';

const API_BASE_URL = "http://localhost:8000/api/events";

const FaceEvents = () => {
  const [cameras, setCameras] = useState(['All Cameras']);
  const [selectedCamera, setSelectedCamera] = useState('All Cameras');
  const [nameFilter, setNameFilter] = useState('');
  const [fromDate, setFromDate] = useState(subDays(new Date(), 7));
  const [toDate, setToDate] = useState(new Date());
  const [faces, setFaces] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadCameras = useCallback(async () => {
    try {
      const cameraUrl = 'http://localhost:8000/api/collections/cameras';
      const response = await axios.get(cameraUrl, {
        timeout: 5000,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      if (response.data.cameras) {
        const cameraNames = response.data.cameras.map(camera => camera.name);
        setCameras(['All Cameras', ...cameraNames]);
      }
    } catch (err) {
    }
  }, []);

  const fetchFaces = useCallback(async (params = {}) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}/filter`, {
        params,
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      return Array.isArray(response.data) ? response.data : [];
    } catch (err) {
      let errorMessage = 'Failed to fetch faces';
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. Please check if the backend server is running.';
      } else if (err.response?.status === 400) {
        errorMessage = err.response.data.detail || 'Invalid request';
      } else if (err.response) {
        errorMessage = `Server error: ${err.response.status} - ${err.response.data?.detail || err.response.statusText}`;
      } else if (err.request) {
        errorMessage = 'Cannot connect to backend server. Please ensure the server is running on http://localhost:8000';
      } else {
        errorMessage = `Error: ${err.message}`;
      }
      setError(errorMessage);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const buildParams = useCallback((overrides = {}) => {
    const params = {
      from_date: format(fromDate, 'yyyy-MM-dd'),
      to_date: format(toDate, 'yyyy-MM-dd'),
      camera: selectedCamera === 'All Cameras' ? 'all_cameras' : selectedCamera,
      ...overrides,
    };
    if (nameFilter.trim()) {
      params.name = nameFilter.trim();
    }
    return params;
  }, [fromDate, toDate, selectedCamera, nameFilter]);

  const ensureValidDates = useCallback(() => {
    if (fromDate > toDate) {
      setError('From date cannot be later than To date');
      return false;
    }
    return true;
  }, [fromDate, toDate]);

  const getTabOverrides = useCallback((tab) => {
    if (tab === 'known') {
      return { face_type: 'known' };
    }
    if (tab === 'unknown') {
      return { face_type: 'unknown' };
    }
    return {};
  }, []);

  const handleFilter = useCallback(async (overrides = {}, targetTab = null) => {
    // Use current activeTab if targetTab is not provided
    const tabToUse = targetTab !== null ? targetTab : activeTab;
    
    if (!ensureValidDates()) {
      return;
    }

    const mergedOverrides = { ...getTabOverrides(tabToUse), ...overrides };
    const params = buildParams(mergedOverrides);
    
    console.log('Filtering with params:', params, 'for tab:', tabToUse);
    const data = await fetchFaces(params);
    console.log('Received faces:', data.length, 'faces');
    
    // Backend already filters by face_type, no need for additional client-side filtering
    setFaces(data);
  }, [ensureValidDates, fetchFaces, buildParams, getTabOverrides, activeTab]);

  const handleTabChange = useCallback((tab) => {
    console.log('Tab changed to:', tab);
    setActiveTab(tab);
    handleFilter({}, tab);
  }, [handleFilter]);

  const refreshData = () => {
    console.log('Refreshing data for tab:', activeTab);
    loadCameras();
    handleFilter({}, activeTab);
  };

  const onSearch = () => {
    handleFilter({}, activeTab);
  };

  const handleCameraChange = (value) => {
    setSelectedCamera(value);
    handleFilter({ camera: value === 'All Cameras' ? 'all_cameras' : value }, activeTab);
  };

  useEffect(() => {
    loadCameras();
    // Load all faces on initial mount
    handleFilter({}, 'all');
  }, []); // Only run once on mount

  return (
    <div className="face-events">
      <div className="navigation-buttons">
        <button
          onClick={() => handleTabChange('all')}
          className={`nav-btn ${activeTab === 'all' ? 'active-btn' : ''}`}
        >
          All Faces
        </button>
        <button
          onClick={() => handleTabChange('known')}
          className={`nav-btn known-btn ${activeTab === 'known' ? 'active-btn' : ''}`}
        >
          Known Faces
        </button>
        <button
          onClick={() => handleTabChange('unknown')}
          className={`nav-btn unknown-btn ${activeTab === 'unknown' ? 'active-btn' : ''}`}
        >
          Unknown Faces
        </button>
        <button onClick={refreshData} className="nav-btn refresh-btn">
          Refresh
        </button>
      </div>

      <div className="filters">
        <div className="filter-group">
          <label>Camera:</label>
          <select
            value={selectedCamera}
            onChange={(e) => handleCameraChange(e.target.value)}
          >
            {cameras.map(camera => (
              <option key={camera} value={camera}>{camera}</option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <label>Name:</label>
          <input
            type="text"
            placeholder="Filter by name..."
            value={nameFilter}
            onChange={(e) => setNameFilter(e.target.value)}
          />
        </div>

        <div className="filter-group">
          <label>From:</label>
          <DatePicker
            selected={fromDate}
            onChange={(date) => setFromDate(date)}
            dateFormat="yyyy-MM-dd"
            className="date-picker"
          />
        </div>

        <div className="filter-group">
          <label>To:</label>
          <DatePicker
            selected={toDate}
            onChange={(date) => setToDate(date)}
            dateFormat="yyyy-MM-dd"
            className="date-picker"
          />
        </div>

        <button onClick={onSearch} className="search-btn">
          Search
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="faces-container">
        {loading ? (
          <div className="loading">Loading faces...</div>
        ) : faces.length > 0 ? (
          <div className="faces-grid">
            {faces.map((face, index) => (
              <FaceCard
                key={`${face.image_path}-${index}`}
                imagePath={face.image_path}
                name={face.name}
                camera={face.camera}
                timestamp={face.timestamp}
              />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            No faces found matching the criteria
          </div>
        )}
      </div>
    </div>
  );
};

export default FaceEvents;
