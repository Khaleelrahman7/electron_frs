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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadCameras = useCallback(async () => {
    try {
      // Fix the URL - remove the double prefix
      const cameraUrl = 'http://localhost:8000/api/collections/cameras';
      console.log('Loading cameras from:', cameraUrl);
      const response = await axios.get(cameraUrl, {
        timeout: 5000,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      console.log('Cameras response:', response.data);
      if (response.data.cameras) {
        const cameraNames = response.data.cameras.map(camera => camera.name);
        setCameras(['All Cameras', ...cameraNames]);
      }
    } catch (err) {
      console.error('Failed to load cameras:', err);
      // Don't show error for cameras, just use default
    }
  }, []);

  const filterFaces = useCallback(async () => {
    if (fromDate > toDate) {
      setError('From date cannot be later than To date');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const params = {
        from_date: format(fromDate, 'yyyy-MM-dd'),
        to_date: format(toDate, 'yyyy-MM-dd'),
        camera: selectedCamera === 'All Cameras' ? 'all_cameras' : selectedCamera
      };

      if (nameFilter.trim()) {
        params.name = nameFilter.trim();
      }

      console.log('Filtering faces with params:', params);
      const response = await axios.get(`${API_BASE_URL}/filter`, { 
        params,
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      console.log('Filter response:', response.data);
      setFaces(response.data);
    } catch (err) {
      console.error('Filter faces error:', err);
      let errorMessage = 'Failed to filter faces';
      
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
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, selectedCamera, nameFilter]);

  const showKnownFaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const camera = selectedCamera === 'All Cameras' ? 'all_cameras' : selectedCamera;
      console.log('Loading known faces for camera:', camera);
      const response = await axios.get(`${API_BASE_URL}/filter`, {
        params: { name: '', camera },
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      const knownFaces = response.data.filter(face => face.name !== 'Unknown');
      console.log('Known faces:', knownFaces);
      setFaces(knownFaces);
    } catch (err) {
      console.error('Known faces error:', err);
      let errorMessage = 'Failed to fetch known faces';
      
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. Please check if the backend server is running.';
      } else if (err.response) {
        errorMessage = `Server error: ${err.response.status} - ${err.response.data?.detail || err.response.statusText}`;
      } else if (err.request) {
        errorMessage = 'Cannot connect to backend server. Please ensure the server is running on http://localhost:8000';
      } else {
        errorMessage = `Error: ${err.message}`;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [selectedCamera]);

  const showUnknownFaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const camera = selectedCamera === 'All Cameras' ? 'all_cameras' : selectedCamera;
      console.log('Loading unknown faces for camera:', camera);
      const response = await axios.get(`${API_BASE_URL}/filter`, {
        params: { name: 'Unknown', camera },
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      console.log('Unknown faces:', response.data);
      setFaces(response.data);
    } catch (err) {
      console.error('Unknown faces error:', err);
      let errorMessage = 'Failed to fetch unknown faces';
      
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. Please check if the backend server is running.';
      } else if (err.response) {
        errorMessage = `Server error: ${err.response.status} - ${err.response.data?.detail || err.response.statusText}`;
      } else if (err.request) {
        errorMessage = 'Cannot connect to backend server. Please ensure the server is running on http://localhost:8000';
      } else {
        errorMessage = `Error: ${err.message}`;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [selectedCamera]);

  useEffect(() => {
    loadCameras();
  }, [loadCameras]);

  return (
    <div className="face-events">
      <div className="navigation-buttons">
        <button onClick={showKnownFaces} className="nav-btn known-btn">
          Known Faces
        </button>
        <button onClick={showUnknownFaces} className="nav-btn unknown-btn">
          Unknown Faces
        </button>
        <button onClick={loadCameras} className="nav-btn refresh-btn">
          Refresh
        </button>
      </div>

      <div className="filters">
        <div className="filter-group">
          <label>Camera:</label>
          <select 
            value={selectedCamera} 
            onChange={(e) => setSelectedCamera(e.target.value)}
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
            onChange={setFromDate}
            dateFormat="yyyy-MM-dd"
            className="date-picker"
          />
        </div>

        <div className="filter-group">
          <label>To:</label>
          <DatePicker
            selected={toDate}
            onChange={setToDate}
            dateFormat="yyyy-MM-dd"
            className="date-picker"
          />
        </div>

        <button onClick={filterFaces} className="search-btn">
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
