import React, { useState, useEffect, useCallback } from 'react';
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
  const [allPersons, setAllPersons] = useState([]);
  const [selectedPerson, setSelectedPerson] = useState(null);
  const [personDetails, setPersonDetails] = useState(null);
  const [personImages, setPersonImages] = useState([]);
  const [personStats, setPersonStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingPerson, setLoadingPerson] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);
    fetchAllAnalytics();
    fetchAllPersons();
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchAllAnalytics();
        if (selectedPerson) {
          fetchPersonDetails(selectedPerson);
        }
      }, 5000);
      setRefreshInterval(interval);
      return () => clearInterval(interval);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [autoRefresh, selectedPerson]);

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

  const fetchAllPersons = async () => {
    try {
      const [personFreqRes, galleryRes] = await Promise.all([
        axios.get(getApiUrl('/api/analytics/person-frequency'), {
          params: { limit: 100 }
        }).catch(() => ({ data: { labels: [], data: [] } })),
        axios.get(getApiUrl('/api/registration/gallery')).catch(() => ({ data: {} }))
      ]);

      const galleryData = galleryRes.data || {};
      const personFreqData = personFreqRes.data || { labels: [], data: [] };
      
      // Create a map of person frequencies
      const frequencyMap = {};
      if (personFreqData.labels && personFreqData.data) {
        personFreqData.labels.forEach((name, idx) => {
          frequencyMap[name] = personFreqData.data[idx] || 0;
        });
      }
      
      // Get all registered users from gallery (even if they have no detections)
      const allRegisteredUsers = Object.keys(galleryData);
      
      // Combine: users with detections + all registered users
      const allUserNames = [...new Set([...personFreqData.labels || [], ...allRegisteredUsers])];
      
      if (allUserNames.length > 0) {
        const persons = allUserNames.map((name) => {
          const personInfo = galleryData[name] || {};
          const imageFilename = personInfo.image_filename || 'original.jpg';
          const imageUrl = `/api/gallery/image/${encodeURIComponent(name)}/${encodeURIComponent(imageFilename)}`;
          
          return {
            name,
            frequency: frequencyMap[name] || 0,
            imageUrl: getApiUrl(imageUrl),
            age: personInfo.age || null,
            gender: personInfo.gender || null,
            category: personInfo.category || null,
            photoPath: personInfo.photo_path || null
          };
        });
        
        // Sort by frequency (descending), then by name
        persons.sort((a, b) => {
          if (b.frequency !== a.frequency) {
            return b.frequency - a.frequency;
          }
          return a.name.localeCompare(b.name);
        });
        
        setAllPersons(persons);
        if (persons.length > 0 && !selectedPerson) {
          setSelectedPerson(persons[0].name);
        }
      }
    } catch (err) {
      console.error('Error fetching persons:', err);
    }
  };

  const fetchPersonDetails = useCallback(async (personName) => {
    if (!personName) {
      setPersonDetails(null);
      setPersonImages([]);
      setPersonStats(null);
      return;
    }
    
    try {
      console.log('Fetching details for:', personName);
      
      const [eventsRes, galleryRes] = await Promise.all([
        axios.get(getApiUrl('/api/events/filter'), {
          params: { name: personName }
        }).catch((err) => {
          console.error('Error fetching events:', err);
          return { data: { faces: [] } };
        }),
        axios.get(getApiUrl('/api/registration/gallery')).catch((err) => {
          console.error('Error fetching gallery:', err);
          return { data: {} };
        })
      ]);

      const personEvents = eventsRes.data?.faces || [];
      const galleryData = galleryRes.data || {};
      const personGallery = galleryData[personName] || {};
      
      console.log('Person gallery data:', personGallery);
      console.log('Person events:', personEvents.length);
      
      // Get gallery image - try multiple fallback options
      let imageFilename = personGallery.image_filename || 'original.jpg';
      let galleryImageUrl = `/api/gallery/image/${encodeURIComponent(personName)}/${encodeURIComponent(imageFilename)}`;
      
      // If no image_filename, try common names
      if (!personGallery.image_filename) {
        const commonNames = ['1.jpg', 'original.jpg', 'face.jpg', 'photo.jpg'];
        imageFilename = commonNames[0];
        galleryImageUrl = `/api/gallery/image/${encodeURIComponent(personName)}/${encodeURIComponent(imageFilename)}`;
      }

      const stats = {
        totalDetections: personEvents.length,
        avgConfidence: personEvents.length > 0
          ? personEvents.reduce((sum, e) => sum + (parseFloat(e.confidence) || 0), 0) / personEvents.length
          : 0,
        lastSeen: personEvents.length > 0 ? personEvents[0].timestamp : null,
        cameras: [...new Set(personEvents.map(e => e.camera || 'Unknown'))],
        recentImages: personEvents.slice(0, 10).map(e => e.image_path || e.image_url || '')
      };

      const fullGalleryImageUrl = getApiUrl(galleryImageUrl);
      
      setPersonDetails({
        name: personName,
        events: personEvents,
        gallery: personGallery,
        stats,
        galleryImageUrl: fullGalleryImageUrl,
        age: personGallery.age || null,
        gender: personGallery.gender || null,
        category: personGallery.category || null
      });
      
      // Use gallery image as primary, fallback to recent detection images
      const primaryImage = fullGalleryImageUrl;
      const detectionImages = personEvents.slice(0, 5).map(e => {
        if (e.image_path) {
          return e.image_path.startsWith('http') ? e.image_path : getApiUrl(e.image_path);
        }
        if (e.image_url) {
          return e.image_url.startsWith('http') ? e.image_url : getApiUrl(e.image_url);
        }
        return '';
      }).filter(Boolean);
      
      setPersonImages([primaryImage, ...detectionImages].filter(Boolean));
      setPersonStats(stats);
      
      console.log('Person details set successfully');
    } catch (err) {
      console.error('Error fetching person details:', err);
      setPersonDetails({
        name: personName,
        events: [],
        gallery: {},
        stats: {
          totalDetections: 0,
          avgConfidence: 0,
          lastSeen: null,
          cameras: [],
          recentImages: []
        },
        galleryImageUrl: null,
        age: null,
        gender: null,
        category: null
      });
      setPersonImages([]);
      setPersonStats({
        totalDetections: 0,
        avgConfidence: 0,
        lastSeen: null,
        cameras: [],
        recentImages: []
      });
    }
  }, []);

  useEffect(() => {
    if (selectedPerson) {
      // Reset person details when switching users
      setPersonDetails(null);
      setPersonImages([]);
      setPersonStats(null);
      setLoadingPerson(true);
      // Fetch new person details
      fetchPersonDetails(selectedPerson).finally(() => {
        setLoadingPerson(false);
      });
    }
  }, [selectedPerson]); // Removed fetchPersonDetails from dependencies to avoid infinite loop

  const fetchPersonAnalytics = async (personName) => {
    try {
      const response = await axios.get(getApiUrl(`/api/analytics/person/${personName}`));
      setPersonAnalytics(response.data);
    } catch (err) {
      console.error('Error fetching person analytics:', err);
      setPersonAnalytics(null);
    }
  };
  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
      tooltip: {
        mode: 'index',
        intersect: false,
      },
    },
    interaction: {
      mode: 'nearest',
      axis: 'x',
      intersect: false
    },
    animation: {
      duration: 750,
      easing: 'easeInOutQuart'
    }
  };

  const getPersonHourlyData = () => {
    if (!personDetails || !personDetails.events) return null;
    const hourlyCounts = Array(24).fill(0);
    personDetails.events.forEach(event => {
      try {
        const date = new Date(event.timestamp);
        const hour = date.getHours();
        hourlyCounts[hour]++;
      } catch (e) {
        // Skip invalid dates
      }
    });
    return {
      labels: Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}:00`),
      datasets: [{
        label: `${selectedPerson} Activity`,
        data: hourlyCounts,
        borderColor: 'rgb(0, 162, 255)',
        backgroundColor: 'rgba(0, 162, 255, 0.2)',
        tension: 0.4,
        fill: true,
      }],
    };
  };

  const getPersonConfidenceData = () => {
    if (!personDetails || !personDetails.events) return null;
    const confidences = personDetails.events
      .map(e => parseFloat(e.confidence) || 0)
      .filter(c => c > 0);
    if (confidences.length === 0) return null;
    
    const ranges = [
      { label: '90-100%', min: 0.9, max: 1.0 },
      { label: '80-90%', min: 0.8, max: 0.9 },
      { label: '70-80%', min: 0.7, max: 0.8 },
      { label: '60-70%', min: 0.6, max: 0.7 },
      { label: '<60%', min: 0, max: 0.6 },
    ];
    
    const counts = ranges.map(range => 
      confidences.filter(c => c >= range.min && c < range.max).length
    );
    
    return {
      labels: ranges.map(r => r.label),
      datasets: [{
        label: 'Confidence Distribution',
        data: counts,
        backgroundColor: [
          'rgba(75, 192, 192, 0.8)',
          'rgba(54, 162, 235, 0.8)',
          'rgba(255, 205, 86, 0.8)',
          'rgba(255, 159, 64, 0.8)',
          'rgba(255, 99, 132, 0.8)',
        ],
        borderWidth: 2,
      }],
    };
  };

  const trendChartData = trendData ? {
    labels: trendData.labels,
    datasets: [
      {
        label: 'Known Faces',
        data: trendData.known,
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        tension: 0.4,
        fill: true,
      },
      {
        label: 'Unknown Faces',
        data: trendData.unknown,
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
        tension: 0.4,
        fill: true,
      },
    ],
  } : null;

  const confidenceChartData = confidenceData ? {
    labels: confidenceData.labels,
    datasets: [{
      label: 'Face Detections',
      data: confidenceData.data,
      backgroundColor: [
        'rgba(255, 99, 132, 0.8)',
        'rgba(255, 159, 64, 0.8)',
        'rgba(255, 205, 86, 0.8)',
        'rgba(75, 192, 192, 0.8)',
        'rgba(54, 162, 235, 0.8)',
      ],
      borderWidth: 2,
    }],
  } : null;

  const personChartData = personData ? {
    labels: personData.labels,
    datasets: [{
      label: 'Recognition Count',
      data: personData.data,
      backgroundColor: 'rgba(54, 162, 235, 0.8)',
      borderColor: 'rgba(54, 162, 235, 1)',
      borderWidth: 2,
    }],
  } : null;

  const hourlyChartData = hourlyData ? {
    labels: hourlyData.labels,
    datasets: [{
      label: 'Face Detections',
      data: hourlyData.data,
      borderColor: 'rgb(153, 102, 255)',
      backgroundColor: 'rgba(153, 102, 255, 0.2)',
      tension: 0.4,
      fill: true,
    }],
  } : null;

  const cameraChartData = cameraData ? {
    labels: cameraData.labels,
    datasets: [{
      data: cameraData.data,
      backgroundColor: [
        'rgba(255, 99, 132, 0.8)',
        'rgba(54, 162, 235, 0.8)',
        'rgba(255, 205, 86, 0.8)',
        'rgba(75, 192, 192, 0.8)',
        'rgba(153, 102, 255, 0.8)',
      ],
      borderWidth: 2,
    }],
  } : null;

  if (loading && !overviewData) {
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
  const personHourlyData = getPersonHourlyData();
  const personConfidenceData = getPersonConfidenceData();

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Face Recognition Analytics</h1>
        <button onClick={fetchDashboardData} className="refresh-button">
          <span className="refresh-icon">↻</span> Refresh
        </button>
        <h2>Face Recognition Dashboard</h2>
        <div className="header-controls">
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <span>Auto Refresh</span>
          </label>
          <button onClick={fetchAllAnalytics} className="refresh-button">
            ↻ Refresh
          </button>
        </div>
      </div>

      <div className="dashboard-content">
        {/* Left Panel - Person Profiles */}
        <div className="left-panel">
          <div className="panel-header">
            <span className="panel-icon">👤</span>
            <span className="panel-title">Profiles</span>
      <div className="dashboard-layout">
        {/* Left Panel - User List */}
        <div className="user-panel">
          <h3>Registered Users</h3>
          <div className="user-list">
            {allPersons.length > 0 ? (
              allPersons.map((person, idx) => (
                <div
                  key={idx}
                  className={`user-item ${selectedPerson === person.name ? 'active' : ''}`}
                  onClick={() => setSelectedPerson(person.name)}
                >
                  <div className="user-avatar">
                    {person.imageUrl ? (
                      <img
                        src={person.imageUrl}
                        alt={person.name}
                        onError={(e) => {
                          e.target.style.display = 'none';
                          e.target.nextSibling.style.display = 'flex';
                        }}
                      />
                    ) : null}
                    <div className="avatar-fallback" style={{ display: person.imageUrl ? 'none' : 'flex' }}>
                      {person.name.charAt(0).toUpperCase()}
                    </div>
                  </div>
                  <div className="user-info">
                    <div className="user-name">{person.name}</div>
                    <div className="user-frequency">{person.frequency} detections</div>
                    {person.category && (
                      <div className="user-category">{person.category}</div>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="no-users">No registered users found</div>
            )}
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
          
          {/* Overall Stats */}
          {overviewData && (
            <div className="overall-stats">
              <h4>Overall Statistics</h4>
              <div className="stat-item">
                <span className="stat-label">Total Faces</span>
                <span className="stat-value">{overviewData.total_faces.toLocaleString()}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Recognition Rate</span>
                <span className="stat-value">{overviewData.recognition_rate.toFixed(1)}%</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Unique Persons</span>
                <span className="stat-value">{overviewData.unique_persons}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Avg Confidence</span>
                <span className="stat-value">{(overviewData.avg_confidence * 100).toFixed(1)}%</span>
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
        {/* Center Panel - Selected User Dashboard */}
        <div className="face-dashboard-panel">
          {loadingPerson ? (
            <div className="person-loading">
              <div className="loading-spinner"></div>
              <p>Loading {selectedPerson}'s data...</p>
            </div>
          ) : selectedPerson && personDetails ? (
            <>
              <div className="face-header">
                <h3>{selectedPerson}'s Face Dashboard</h3>
                <div className="face-status">
                  <span className="status-indicator active"></span>
                  <span>Active</span>
                </div>
              </div>

              {/* Person Info Header */}
              {personDetails && (
                <div className="person-info-header">
                  <div className="person-basic-info">
                    {personDetails.age && (
                      <div className="info-badge">
                        <span className="info-label">Age</span>
                        <span className="info-value">{personDetails.age}</span>
                      </div>
                    )}
                    {personDetails.gender && (
                      <div className="info-badge">
                        <span className="info-label">Gender</span>
                        <span className="info-value">{personDetails.gender}</span>
                      </div>
                    )}
                    {personDetails.category && (
                      <div className="info-badge">
                        <span className="info-label">Category</span>
                        <span className="info-value">{personDetails.category}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Main Face Display */}
              <div className="face-display-container">
                {personImages.length > 0 ? (
                  <div className="face-image-wrapper">
                    <img
                      src={personImages[0]}
                      alt={selectedPerson}
                      className="face-image"
                      onError={(e) => {
                        e.target.style.display = 'none';
                        const placeholder = e.target.parentElement.querySelector('.face-placeholder');
                        if (placeholder) placeholder.style.display = 'flex';
                      }}
                    />
                    <div className="face-placeholder" style={{ display: 'none' }}>
                      <div className="placeholder-icon">👤</div>
                      <p>No face image available</p>
                    </div>
                    <div className="face-detection-frame"></div>
                    <div className="face-landmarks">
                      {[...Array(20)].map((_, i) => {
                        const angle = (i / 20) * 360;
                        const radius = 35 + (i % 3) * 5;
                        const x = 50 + radius * Math.cos((angle * Math.PI) / 180);
                        const y = 50 + radius * Math.sin((angle * Math.PI) / 180);
                        return (
                          <div
                            key={i}
                            className="landmark-dot"
                            style={{
                              left: `${x}%`,
                              top: `${y}%`,
                            }}
                          ></div>
                        );
                      })}
                    </div>
                    <div className="face-overlay-info">
                      <div className="overlay-badge">
                        <span className="badge-icon">✓</span>
                        <span>Verified</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="face-placeholder">
                    <div className="placeholder-icon">👤</div>
                    <p>No face image available</p>
                  </div>
                )}

                {/* User Metrics */}
                {personStats && (
                  <div className="user-metrics">
                    <div className="metric-card">
                      <div className="metric-icon">📊</div>
                      <div className="metric-content">
                        <div className="metric-label">Total Detections</div>
                        <div className="metric-value">{personStats.totalDetections}</div>
                      </div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-icon">🎯</div>
                      <div className="metric-content">
                        <div className="metric-label">Avg Confidence</div>
                        <div className="metric-value">{(personStats.avgConfidence * 100).toFixed(1)}%</div>
                      </div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-icon">📹</div>
                      <div className="metric-content">
                        <div className="metric-label">Cameras</div>
                        <div className="metric-value">{personStats.cameras.length}</div>
                      </div>
                    </div>
                    <div className="metric-card">
                      <div className="metric-icon">🕒</div>
                      <div className="metric-content">
                        <div className="metric-label">Last Seen</div>
                        <div className="metric-value">
                          {personStats.lastSeen
                            ? new Date(personStats.lastSeen).toLocaleString()
                            : 'Never'}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* Charts for Selected User */}
              <div className="user-charts">
                <div className="chart-container">
                  <h4>Hourly Activity Pattern</h4>
                  {personHourlyData ? (
                    <div className="chart-wrapper">
                      <Line data={personHourlyData} options={chartOptions} />
                    </div>
                  ) : (
                    <div className="no-data">No activity data available</div>
                  )}
                </div>

                <div className="chart-container">
                  <h4>Confidence Distribution</h4>
                  {personConfidenceData ? (
                    <div className="chart-wrapper">
                      <Bar data={personConfidenceData} options={chartOptions} />
                    </div>
                  ) : (
                    <div className="no-data">No confidence data available</div>
                  )}
                </div>
              </div>

              {/* Recent Images Gallery */}
              {personImages.length > 0 && (
                <div className="recent-images">
                  <h4>Recent Detections</h4>
                  <div className="image-gallery">
                    {personImages.map((img, idx) => (
                      <div key={idx} className="gallery-item">
                        <img
                          src={img.startsWith('http') ? img : getApiUrl(img)}
                          alt={`Detection ${idx + 1}`}
                          onError={(e) => {
                            e.target.style.display = 'none';
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="no-selection">
              <div className="no-selection-icon">👥</div>
              <h3>Select a user to view their face dashboard</h3>
              <p>Choose a user from the left panel to see detailed analytics</p>
            </div>
          )}
        </div>

        {/* Right Panel - Analytics */}
        <div className="analytics-panel">
          <h3>System Analytics</h3>
          
          {/* Trend Chart */}
          <div className="chart-container">
            <h4>Face Detection Trend</h4>
            {trendChartData ? (
              <div className="chart-wrapper">
                <Line data={trendChartData} options={chartOptions} />
              </div>
            ) : (
              <div className="no-data">No trend data</div>
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
          {/* Person Frequency */}
          <div className="chart-container">
            <h4>Top Recognized Persons</h4>
            {personChartData ? (
              <div className="chart-wrapper">
                <Bar data={personChartData} options={chartOptions} />
              </div>
            ) : (
              <div className="no-data">No person data</div>
            )}
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
          {/* Camera Activity */}
          <div className="chart-container">
            <h4>Camera Activity</h4>
            {cameraChartData ? (
              <div className="chart-wrapper">
                <Pie data={cameraChartData} options={chartOptions} />
              </div>
            ) : (
              <div className="no-data">No camera data</div>
            )}
          </div>
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
