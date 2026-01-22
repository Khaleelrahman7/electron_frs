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
      
      // Fix image URLs in persons list if they contain localhost
      const persons = Array.isArray(personsRes.data) ? personsRes.data.map(person => {
        if (person.profile_image && person.profile_image.includes('localhost')) {
          // Replace localhost:8005 with configured API URL
          const currentApiUrl = getApiUrl('');
          // Remove trailing slash if present
          const baseUrl = currentApiUrl.endsWith('/') ? currentApiUrl.slice(0, -1) : currentApiUrl;
          
          return {
            ...person,
            profile_image: person.profile_image.replace(/http:\/\/localhost:\d+/, baseUrl)
          };
        }
        return person;
      }) : [];
      
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

      {/* Charts Section */}
      <div className="charts-section">
        <div className="charts-header">
          <h2 className="charts-title">Advanced Analytics</h2>
        </div>
        <div className="charts-grid">
          {/* Daily Trend Chart */}
          <div className="chart-card">
            <div className="chart-header">
              <h3 className="chart-title">Detection Trend (7 Days)</h3>
            </div>
            <div className="chart-wrapper">
              {trendData && trendData.labels ? (
                <Line
                  data={{
                    labels: trendData.labels,
                    datasets: [
                      {
                        label: 'Known Faces',
                        data: trendData.known,
                        borderColor: '#4FC3F7',
                        backgroundColor: 'rgba(79, 195, 247, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#4FC3F7',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                      },
                      {
                        label: 'Unknown Faces',
                        data: trendData.unknown,
                        borderColor: '#FF6B6B',
                        backgroundColor: 'rgba(255, 107, 107, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#FF6B6B',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                      },
                    ],
                  }}
                  options={getChartOptions('Detection Trend')}
                />
              ) : (
                <div className="no-chart-data">No trend data available</div>
              )}
            </div>
          </div>

          {/* Hourly Activity Chart */}
          <div className="chart-card">
            <div className="chart-header">
              <h3 className="chart-title">Hourly Activity Pattern</h3>
            </div>
            <div className="chart-wrapper">
              {hourlyData && hourlyData.labels ? (
                <Bar
                  data={{
                    labels: hourlyData.labels,
                    datasets: [
                      {
                        label: 'Detections',
                        data: hourlyData.data,
                        backgroundColor: 'rgba(79, 195, 247, 0.8)',
                        borderColor: '#4FC3F7',
                        borderWidth: 1,
                        borderRadius: 8,
                        borderSkipped: false,
                      },
                    ],
                  }}
                  options={getChartOptions('Hourly Activity')}
                />
              ) : (
                <div className="no-chart-data">No hourly data available</div>
              )}
            </div>
          </div>

          {/* Camera Distribution Chart */}
          <div className="chart-card">
            <div className="chart-header">
              <h3 className="chart-title">Camera Distribution</h3>
            </div>
            <div className="chart-wrapper">
              {cameraData && cameraData.labels && cameraData.labels.length > 0 ? (
                <Doughnut
                  data={{
                    labels: cameraData.labels,
                    datasets: [
                      {
                        data: cameraData.data,
                        backgroundColor: [
                          'rgba(79, 195, 247, 0.8)',
                          'rgba(255, 107, 107, 0.8)',
                          'rgba(255, 206, 86, 0.8)',
                          'rgba(75, 192, 192, 0.8)',
                          'rgba(153, 102, 255, 0.8)',
                          'rgba(255, 159, 64, 0.8)',
                        ],
                        borderColor: [
                          '#4FC3F7',
                          '#FF6B6B',
                          '#FFCE56',
                          '#4BC0C0',
                          '#9966FF',
                          '#FF9F40',
                        ],
                        borderWidth: 2,
                      },
                    ],
                  }}
                  options={getDoughnutOptions()}
                />
              ) : (
                <div className="no-chart-data">No camera data available</div>
              )}
            </div>
          </div>

          {/* Confidence Distribution Chart */}
          <div className="chart-card">
            <div className="chart-header">
              <h3 className="chart-title">Confidence Distribution</h3>
            </div>
            <div className="chart-wrapper">
              {confidenceData && confidenceData.labels ? (
                <Bar
                  data={{
                    labels: confidenceData.labels,
                    datasets: [
                      {
                        label: 'Count',
                        data: confidenceData.data,
                        backgroundColor: [
                          'rgba(255, 107, 107, 0.8)',
                          'rgba(255, 159, 64, 0.8)',
                          'rgba(255, 206, 86, 0.8)',
                          'rgba(75, 192, 192, 0.8)',
                          'rgba(79, 195, 247, 0.8)',
                        ],
                        borderColor: [
                          '#FF6B6B',
                          '#FF9F40',
                          '#FFCE56',
                          '#4BC0C0',
                          '#4FC3F7',
                        ],
                        borderWidth: 2,
                        borderRadius: 8,
                      },
                    ],
                  }}
                  options={getChartOptions('Confidence Distribution')}
                />
              ) : (
                <div className="no-chart-data">No confidence data available</div>
              )}
            </div>
          </div>

          {/* Person Frequency Chart */}
          <div className="chart-card">
            <div className="chart-header">
              <h3 className="chart-title">Top Recognized Persons</h3>
            </div>
            <div className="chart-wrapper">
              {personFrequencyData && personFrequencyData.labels ? (
                <Bar
                  data={{
                    labels: personFrequencyData.labels,
                    datasets: [
                      {
                        label: 'Detections',
                        data: personFrequencyData.data,
                        backgroundColor: 'rgba(79, 195, 247, 0.8)',
                        borderColor: '#4FC3F7',
                        borderWidth: 2,
                        borderRadius: 8,
                      },
                    ],
                  }}
                  options={getChartOptions('Person Frequency', true)}
                />
              ) : (
                <div className="no-chart-data">No person frequency data available</div>
              )}
            </div>
          </div>

          {/* Person Daily Activity (if person selected) */}
          {personAnalytics && personAnalytics.daily_distribution ? (
            <div className="chart-card">
              <div className="chart-header">
                <h3 className="chart-title">{selectedPerson} - Daily Activity</h3>
              </div>
              <div className="chart-wrapper">
                <Line
                  data={{
                    labels: personAnalytics.daily_distribution.labels,
                    datasets: [
                      {
                        label: 'Detections',
                        data: personAnalytics.daily_distribution.data,
                        borderColor: '#4FC3F7',
                        backgroundColor: 'rgba(79, 195, 247, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#4FC3F7',
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                      },
                    ],
                  }}
                  options={getChartOptions('Daily Activity')}
                />
              </div>
            </div>
          ) : null}

          {/* Person Hourly Distribution (if person selected) */}
          {personAnalytics && personAnalytics.hourly_distribution ? (
            <div className="chart-card">
              <div className="chart-header">
                <h3 className="chart-title">{selectedPerson} - Hourly Distribution</h3>
              </div>
              <div className="chart-wrapper">
                <Bar
                  data={{
                    labels: Array.from({ length: 24 }, (_, i) => `${i}:00`),
                    datasets: [
                      {
                        label: 'Detections',
                        data: personAnalytics.hourly_distribution,
                        backgroundColor: (context) => {
                          const value = context.parsed.y;
                          const max = Math.max(...personAnalytics.hourly_distribution);
                          const intensity = value / max;
                          return `rgba(79, 195, 247, ${0.3 + intensity * 0.7})`;
                        },
                        borderColor: '#4FC3F7',
                        borderWidth: 1,
                        borderRadius: 6,
                      },
                    ],
                  }}
                  options={getChartOptions('Hourly Distribution')}
                />
              </div>
            </div>
          ) : null}
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

const getChartOptions = (title, horizontal = false) => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'top',
      labels: {
        color: '#ffffff',
        font: {
          size: 12,
          weight: '500',
        },
        padding: 15,
        usePointStyle: true,
        pointStyle: 'circle',
      },
    },
    tooltip: {
      backgroundColor: 'rgba(26, 47, 74, 0.95)',
      titleColor: '#ffffff',
      bodyColor: '#4FC3F7',
      borderColor: 'rgba(79, 195, 247, 0.3)',
      borderWidth: 1,
      padding: 12,
      displayColors: true,
      callbacks: {
        label: function(context) {
          return `${context.dataset.label}: ${context.parsed.y || context.parsed.x}`;
        },
      },
    },
  },
  scales: horizontal ? {
    x: {
      beginAtZero: true,
      ticks: {
        color: 'rgba(255, 255, 255, 0.6)',
        font: {
          size: 11,
        },
      },
      grid: {
        color: 'rgba(79, 195, 247, 0.1)',
        drawBorder: false,
      },
    },
    y: {
      ticks: {
        color: 'rgba(255, 255, 255, 0.6)',
        font: {
          size: 11,
        },
      },
      grid: {
        color: 'rgba(79, 195, 247, 0.1)',
        drawBorder: false,
      },
    },
  } : {
    x: {
      ticks: {
        color: 'rgba(255, 255, 255, 0.6)',
        font: {
          size: 11,
        },
      },
      grid: {
        color: 'rgba(79, 195, 247, 0.1)',
        drawBorder: false,
      },
    },
    y: {
      beginAtZero: true,
      ticks: {
        color: 'rgba(255, 255, 255, 0.6)',
        font: {
          size: 11,
        },
      },
      grid: {
        color: 'rgba(79, 195, 247, 0.1)',
        drawBorder: false,
      },
    },
  },
});

const getDoughnutOptions = () => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      position: 'right',
      labels: {
        color: '#ffffff',
        font: {
          size: 12,
          weight: '500',
        },
        padding: 15,
        usePointStyle: true,
        pointStyle: 'circle',
      },
    },
    tooltip: {
      backgroundColor: 'rgba(26, 47, 74, 0.95)',
      titleColor: '#ffffff',
      bodyColor: '#4FC3F7',
      borderColor: 'rgba(79, 195, 247, 0.3)',
      borderWidth: 1,
      padding: 12,
      callbacks: {
        label: function(context) {
          const label = context.label || '';
          const value = context.parsed || 0;
          const total = context.dataset.data.reduce((a, b) => a + b, 0);
          const percentage = ((value / total) * 100).toFixed(1);
          return `${label}: ${value} (${percentage}%)`;
        },
      },
    },
  },
});

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
