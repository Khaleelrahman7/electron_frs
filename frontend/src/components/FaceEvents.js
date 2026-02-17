import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import DatePicker from 'react-datepicker';
import { format, subDays, differenceInDays } from 'date-fns';
import { 
  Search, 
  X, 
  Download, 
  List, 
  Grid, 
  Calendar, 
  Filter,
  User,
  Camera,
  ChevronDown
} from 'lucide-react';
import FaceCard from './FaceCard';
import "react-datepicker/dist/react-datepicker.css";
import './FaceEvents.css';

import { API_BASE_URL as BASE_URL, fixImageUrl } from '../utils/apiConfig';
const API_BASE_URL = `${BASE_URL}/api/events`;

const FaceEvents = () => {
  // Filter States
  const [cameras, setCameras] = useState(['All Cameras']);
  const [selectedCamera, setSelectedCamera] = useState('All Cameras');
  const [nameFilter, setNameFilter] = useState('');
  const [fromDate, setFromDate] = useState(subDays(new Date(), 7));
  const [toDate, setToDate] = useState(new Date());
  
  // Data States
  const [faces, setFaces] = useState([]);
  const [activeTab, setActiveTab] = useState('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'grid'

  // Helper to calculate date range text
  const getDateRangeText = () => {
    if (!fromDate || !toDate) return '';
    const days = differenceInDays(toDate, fromDate);
    return `Date range: ${days} days selected`;
  };

  const loadCameras = useCallback(async () => {
    try {
      const cameraUrl = `${BASE_URL}/api/collections/cameras`;
      const response = await axios.get(cameraUrl, {
        timeout: 5000,
        headers: { 'Content-Type': 'application/json' }
      });
      if (response.data.cameras) {
        const cameraNames = response.data.cameras.map(camera => camera.name);
        setCameras(['All Cameras', ...cameraNames]);
      }
    } catch (err) {
      console.error("Failed to load cameras", err);
    }
  }, []);

  const fetchFaces = useCallback(async (params = {}) => {
    setLoading(true);
    setError(null);
    try {
      const response = await axios.get(`${API_BASE_URL}/filter`, {
        params,
        timeout: 10000,
        headers: { 'Content-Type': 'application/json' }
      });
      return Array.isArray(response.data) ? response.data : [];
    } catch (err) {
      let errorMessage = 'Failed to fetch faces';
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. Please check if the backend server is running.';
      } else if (err.response?.status === 400) {
        errorMessage = err.response.data.detail || 'Invalid request';
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

  const getTabOverrides = useCallback((tab) => {
    if (tab === 'known') return { face_type: 'known' };
    if (tab === 'unknown') return { face_type: 'unknown' };
    return {};
  }, []);

  const handleFilter = useCallback(async (overrides = {}, targetTab = null) => {
    const tabToUse = targetTab !== null ? targetTab : activeTab;
    
    if (fromDate > toDate) {
      setError('From date cannot be later than To date');
      return;
    }

    const mergedOverrides = { ...getTabOverrides(tabToUse), ...overrides };
    const params = buildParams(mergedOverrides);
    
    const data = await fetchFaces(params);
    setFaces(data);
  }, [fromDate, toDate, fetchFaces, buildParams, getTabOverrides, activeTab]);

  const handleTabChange = useCallback((tab) => {
    setActiveTab(tab);
    handleFilter({}, tab);
  }, [handleFilter]);

  const onSearch = () => {
    handleFilter({}, activeTab);
  };

  const onClear = () => {
    setSelectedCamera('All Cameras');
    setNameFilter('');
    setFromDate(subDays(new Date(), 7));
    setToDate(new Date());
    // Optionally trigger search immediately after clear
    // handleFilter({ camera: 'all_cameras', name: '', from_date: ..., to_date: ... }, activeTab);
  };

  const removeFilter = (type) => {
    if (type === 'camera') setSelectedCamera('All Cameras');
    if (type === 'date') {
      setFromDate(subDays(new Date(), 7));
      setToDate(new Date());
    }
    // Trigger re-fetch? Usually users expect re-fetch.
    // implementing naive re-fetch for now
    setTimeout(() => onSearch(), 0);
  };

  useEffect(() => {
    loadCameras();
    handleFilter({}, 'all');
  }, []);

  return (
    <div className="face-events-page">
      {/* Tabs */}
      <div className="face-events-tabs">
        <button 
          className={`face-events-tab ${activeTab === 'all' ? 'active' : ''}`}
          onClick={() => handleTabChange('all')}
        >
          <span className="dot all"></span> All Faces
        </button>
        <button 
          className={`face-events-tab ${activeTab === 'known' ? 'active' : ''}`}
          onClick={() => handleTabChange('known')}
        >
          Known Faces
        </button>
        <button 
          className={`face-events-tab ${activeTab === 'unknown' ? 'active' : ''}`}
          onClick={() => handleTabChange('unknown')}
        >
          Unknown Faces
        </button>
      </div>

      {/* Filter Card */}
      <div className="filter-card">
        <div className="filter-row">
          <div className="filter-group">
            <label><Camera size={14} /> CAMERA</label>
            <div className="select-wrapper">
              <select 
                value={selectedCamera} 
                onChange={(e) => setSelectedCamera(e.target.value)}
              >
                {cameras.map(camera => (
                  <option key={camera} value={camera}>{camera}</option>
                ))}
              </select>
              <ChevronDown size={14} className="select-arrow" />
            </div>
          </div>

          <div className="filter-group">
            <label><User size={14} /> NAME</label>
            <div className="input-wrapper">
              <Search size={14} className="input-icon" />
              <input 
                type="text" 
                placeholder="Filter by name..." 
                value={nameFilter}
                onChange={(e) => setNameFilter(e.target.value)}
              />
            </div>
          </div>

          <div className="filter-group">
            <label><Calendar size={14} /> FROM</label>
            <div className="date-wrapper">
              <DatePicker
                selected={fromDate}
                onChange={date => setFromDate(date)}
                dateFormat="dd-MM-yyyy"
                maxDate={toDate}
                className="custom-datepicker"
              />
              <Calendar size={14} className="date-icon" />
            </div>
          </div>

          <div className="filter-group">
            <label><Calendar size={14} /> TO</label>
            <div className="date-wrapper">
              <DatePicker
                selected={toDate}
                onChange={date => setToDate(date)}
                dateFormat="dd-MM-yyyy"
                minDate={fromDate}
                maxDate={new Date()}
                className="custom-datepicker"
              />
              <Calendar size={14} className="date-icon" />
            </div>
          </div>
        </div>

        <div className="filter-footer">
          <span className="date-range-info">
            <ClockIcon /> {getDateRangeText()}
          </span>
          <div className="action-buttons">
            <button className="btn-clear" onClick={onClear}>
              <X size={14} /> Clear
            </button>
            <button className="btn-search" onClick={onSearch}>
              <Search size={14} /> Search Events
            </button>
          </div>
        </div>
      </div>

      {/* Active Filters */}
      <div className="active-filters-bar">
        {selectedCamera !== 'All Cameras' && (
          <div className="filter-chip">
            <span className="chip-label">Camera:</span> 
            <span className="chip-value">{selectedCamera}</span>
            <button onClick={() => removeFilter('camera')}><X size={12} /></button>
          </div>
        )}
        <div className="filter-chip">
          <span className="chip-label">Date:</span> 
          <span className="chip-value">
            {format(fromDate, 'yyyy-MM-dd')} &rarr; {format(toDate, 'yyyy-MM-dd')}
          </span>
          <button onClick={() => removeFilter('date')}><X size={12} /></button>
        </div>
      </div>

      {/* Results Section */}
      <div className="results-card">
        <div className="results-header">
          <div className="header-left">
            <div className="icon-box"><List size={18} /></div>
            <div className="title-group">
              <h3>Event Results</h3>
              <span className="count">{faces.length} records found</span>
            </div>
          </div>
          <div className="view-actions">
            <button className="action-icon-btn" title="Download">
              <Download size={18} />
            </button>
            <div className="view-toggle">
              <button 
                className={`toggle-btn ${viewMode === 'list' ? 'active' : ''}`}
                onClick={() => setViewMode('list')}
              >
                <List size={18} />
              </button>
              <button 
                className={`toggle-btn ${viewMode === 'grid' ? 'active' : ''}`}
                onClick={() => setViewMode('grid')}
              >
                <Grid size={18} />
              </button>
            </div>
          </div>
        </div>

        {error && <div className="error-message">{error}</div>}

        <div className="results-content">
          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <p>Loading events...</p>
            </div>
          ) : faces.length === 0 ? (
            <div className="empty-state">
              <Search size={48} />
              <p>No records found</p>
            </div>
          ) : viewMode === 'list' ? (
            <div className="table-responsive">
              <table className="events-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>NAME</th>
                    <th>CAMERA</th>
                    <th>DATE & TIME</th>
                    <th>TYPE</th>
                    <th>CONFIDENCE</th>
                    <th>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {faces.map((face, index) => (
                    <tr key={`${face.image_path}-${index}`}>
                      <td>{index + 1}</td>
                      <td>
                        <div className="user-cell">
                          <div className="avatar-small">
                            <img 
                              src={fixImageUrl(face.image_path)} 
                              alt={face.name}
                              onError={(e) => {e.target.style.display='none'}} 
                            />
                          </div>
                          <span>{face.name}</span>
                        </div>
                      </td>
                      <td>{face.camera}</td>
                      <td>{format(new Date(face.timestamp), 'yyyy-MM-dd HH:mm:ss')}</td>
                      <td>
                        <span className={`badge ${face.name === 'Unknown' ? 'badge-unknown' : 'badge-known'}`}>
                          {face.name === 'Unknown' ? 'Unknown' : 'Known'}
                        </span>
                      </td>
                      <td>
                        {face.confidence !== undefined && face.confidence !== null ? (
                          <div className="confidence-bar">
                            <div 
                              className="fill" 
                              style={{width: `${face.confidence * 100}%`}}
                            ></div>
                            <span>{(face.confidence * 100).toFixed(1)}%</span>
                          </div>
                        ) : (
                          <span className="text-muted">-</span>
                        )}
                      </td>
                      <td>
                        <button className="btn-action">View</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
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
          )}
        </div>
      </div>
    </div>
  );
};

const ClockIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"></circle>
    <polyline points="12 6 12 12 16 14"></polyline>
  </svg>
);

export default FaceEvents;
