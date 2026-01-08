import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getApiUrl } from '../../utils/apiConfig';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Bar, Line, Doughnut, Pie } from 'react-chartjs-2';
import './Dashboard.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const Dashboard = () => {
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [personsList, setPersonsList] = useState([]);
  const [personAnalytics, setPersonAnalytics] = useState(null);
  const [overviewData, setOverviewData] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [hourlyData, setHourlyData] = useState(null);
  const [cameraData, setCameraData] = useState(null);
  const [confidenceData, setConfidenceData] = useState(null);
  const [personFrequencyData, setPersonFrequencyData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  useEffect(() => {
    if (selectedPerson) {
      fetchPersonAnalytics(selectedPerson);
    }
  }, [selectedPerson]);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      const [
        overviewRes,
        personsRes,
        trendRes,
        hourlyRes,
        cameraRes,
        confidenceRes,
        personFreqRes
      ] = await Promise.all([
        axios.get(getApiUrl('/api/analytics/overview')),
        axios.get(getApiUrl('/api/analytics/persons-list')),
        axios.get(getApiUrl('/api/analytics/face-detection-trend?days=7')),
        axios.get(getApiUrl('/api/analytics/hourly-activity')),
        axios.get(getApiUrl('/api/analytics/camera-activity')),
        axios.get(getApiUrl('/api/analytics/confidence-distribution')),
        axios.get(getApiUrl('/api/analytics/person-frequency?limit=10'))
      ]);

      setOverviewData(overviewRes.data);
      const persons = Array.isArray(personsRes.data) ? personsRes.data : [];
      setPersonsList(persons);
      setTrendData(trendRes.data);
      setHourlyData(hourlyRes.data);
      setCameraData(cameraRes.data);
      setConfidenceData(confidenceRes.data);
      setPersonFrequencyData(personFreqRes.data);
      
      // Auto-select first person if available
      if (persons.length > 0 && !selectedPerson) {
        setSelectedPerson(persons[0].name);
      } else if (persons.length === 0) {
        setSelectedPerson(null);
      }
    } catch (err) {
      setError('Failed to load dashboard data');
      console.error('Dashboard error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchPersonAnalytics = async (personName) => {
    try {
      const response = await axios.get(getApiUrl(`/api/analytics/person/${personName}`));
      setPersonAnalytics(response.data);
    } catch (err) {
      console.error('Error fetching person analytics:', err);
      setPersonAnalytics(null);
    }
  };

  if (loading) {
    return (
      <div className="dashboard-container">
        <div className="dashboard-loading">
          <div className="loading-spinner"></div>
          <p>Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-container">
        <div className="dashboard-error">
          <h3>Error Loading Dashboard</h3>
          <p>{error}</p>
          <button onClick={fetchDashboardData} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const selectedPersonData = personsList.find(p => p.name === selectedPerson);

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Face Recognition Analytics</h1>
        <button onClick={fetchDashboardData} className="refresh-button">
          <span className="refresh-icon">↻</span> Refresh
        </button>
      </div>

      <div className="dashboard-content">
        {/* Left Panel - Person Profiles */}
        <div className="left-panel">
          <div className="panel-header">
            <span className="panel-icon">👤</span>
            <span className="panel-title">Profiles</span>
          </div>
          <div className="profiles-list">
            {personsList.length > 0 ? (
              personsList.slice(0, 10).map((person, index) => (
                <div
                  key={index}
                  className={`profile-item ${selectedPerson === person.name ? 'active' : ''}`}
                  onClick={() => setSelectedPerson(person.name)}
                >
                  <div className="profile-avatar">
                    {person.profile_image ? (
                      <img src={person.profile_image} alt={person.name} />
                    ) : (
                      <div className="profile-placeholder">{person.name.charAt(0).toUpperCase()}</div>
                    )}
                  </div>
                  <div className="profile-info">
                    <div className="profile-name">{person.name}</div>
                    <div className="profile-stats">
                      <span>{person.count} detections</span>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="no-profiles">No persons found</div>
            )}
          </div>
          
          {/* Progress Circle */}
          {overviewData && (
            <div className="progress-circle-container">
              <div className="progress-circle">
                <svg viewBox="0 0 120 120" className="progress-svg">
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth="8"
                  />
                  <circle
                    cx="60"
                    cy="60"
                    r="50"
                    fill="none"
                    stroke="#4FC3F7"
                    strokeWidth="8"
                    strokeDasharray={`${overviewData.recognition_rate * 3.14} 314`}
                    strokeDashoffset="0"
                    transform="rotate(-90 60 60)"
                    className="progress-bar"
                  />
                </svg>
                <div className="progress-text">
                  <div className="progress-value">{overviewData.recognition_rate.toFixed(0)}%</div>
                  <div className="progress-label">Recognition</div>
                </div>
              </div>
              <div className="progress-stats">
                <div className="stat-item">
                  <div className="stat-value">{overviewData.total_faces}</div>
                  <div className="stat-label">Total</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{overviewData.unique_persons}</div>
                  <div className="stat-label">Persons</div>
                </div>
                <div className="stat-item">
                  <div className="stat-value">{overviewData.avg_confidence.toFixed(2)}</div>
                  <div className="stat-label">Confidence</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Center Panel - Main Face Display */}
        <div className="center-panel">
          {selectedPersonData && personAnalytics ? (
            <>
              <div className="face-display-container">
                <div className="face-frame">
                  {selectedPersonData.profile_image ? (
                    <img 
                      src={selectedPersonData.profile_image} 
                      alt={selectedPersonData.name}
                      className="main-face-image"
                    />
                  ) : (
                    <div className="face-placeholder">
                      <div className="placeholder-icon">👤</div>
                      <div className="placeholder-text">{selectedPersonData.name}</div>
                    </div>
                  )}
                  <div className="face-overlay">
                    <div className="face-detection-box"></div>
                    <div className="face-landmarks">
                      {[...Array(5)].map((_, i) => (
                        <div key={i} className="landmark-dot" style={{
                          left: `${20 + i * 15}%`,
                          top: `${30 + (i % 2) * 20}%`
                        }}></div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <div className="person-name-display">{selectedPersonData.name}</div>
            </>
          ) : (
            <div className="no-selection">
              <div className="no-selection-icon">👤</div>
              <div className="no-selection-text">Select a person to view analytics</div>
            </div>
          )}
        </div>

        {/* Right Panel - Metrics */}
        <div className="right-panel">
          <div className="panel-header">
            <span className="panel-icon">📊</span>
            <span className="panel-title">Metrics</span>
          </div>
          {personAnalytics ? (
            <div className="metrics-container">
              <MetricBar
                label="Dynamic Recognition"
                value={personAnalytics.dynamic_recognition}
                max={100}
              />
              <MetricBar
                label="Output Intensity"
                value={personAnalytics.output_intensity}
                max={100}
              />
              <MetricBar
                label="Output Volume"
                value={personAnalytics.output_volume}
                max={Math.max(100, personAnalytics.output_volume)}
              />
              <MetricBar
                label="Basic Information"
                value={personAnalytics.basic_info}
                max={100}
              />
              <div className="metric-details">
                <div className="detail-item">
                  <span className="detail-label">Total Detections:</span>
                  <span className="detail-value">{personAnalytics.total_detections}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Avg Confidence:</span>
                  <span className="detail-value">{(personAnalytics.avg_confidence * 100).toFixed(1)}%</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">Cameras:</span>
                  <span className="detail-value">{Object.keys(personAnalytics.camera_distribution || {}).length}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="no-metrics">No metrics available</div>
          )}
        </div>
      </div>

      {/* Bottom Controls */}
      <div className="bottom-controls">
        <button className="control-button">
          <span className="control-icon">✋</span>
          <span className="control-label">Manual</span>
        </button>
        <button className="control-button">
          <span className="control-icon">☁</span>
          <span className="control-label">Cloud</span>
        </button>
        <button className="control-button">
          <span className="control-icon">⚙</span>
          <span className="control-label">Settings</span>
        </button>
      </div>
    </div>
  );
};

const MetricBar = ({ label, value, max }) => {
  const percentage = Math.min(100, (value / max) * 100);
  
  return (
    <div className="metric-bar-container">
      <div className="metric-label">{label}</div>
      <div className="metric-bar-wrapper">
        <div 
          className="metric-bar" 
          style={{ width: `${percentage}%` }}
        >
          <div className="metric-bar-fill"></div>
        </div>
        <span className="metric-value">{value}</span>
      </div>
    </div>
  );
};

export default Dashboard;
