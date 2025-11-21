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
  Legend
);

const Dashboard = () => {
  const [overviewData, setOverviewData] = useState(null);
  const [trendData, setTrendData] = useState(null);
  const [confidenceData, setConfidenceData] = useState(null);
  const [personData, setPersonData] = useState(null);
  const [hourlyData, setHourlyData] = useState(null);
  const [cameraData, setCameraData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchAllAnalytics();
  }, []);

  const fetchAllAnalytics = async () => {
    try {
      setLoading(true);
      const [
        overviewRes,
        trendRes,
        confidenceRes,
        personRes,
        hourlyRes,
        cameraRes
      ] = await Promise.all([
        axios.get(getApiUrl('/api/analytics/overview')),
        axios.get(getApiUrl('/api/analytics/face-detection-trend')),
        axios.get(getApiUrl('/api/analytics/confidence-distribution')),
        axios.get(getApiUrl('/api/analytics/person-frequency')),
        axios.get(getApiUrl('/api/analytics/hourly-activity')),
        axios.get(getApiUrl('/api/analytics/camera-activity'))
      ]);

      setOverviewData(overviewRes.data);
      setTrendData(trendRes.data);
      setConfidenceData(confidenceRes.data);
      setPersonData(personRes.data);
      setHourlyData(hourlyRes.data);
      setCameraData(cameraRes.data);
    } catch (err) {
      setError('Failed to load analytics data');
      console.error('Analytics error:', err);
    } finally {
      setLoading(false);
    }
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
      },
    },
  };

  const trendChartData = trendData ? {
    labels: trendData.labels,
    datasets: [
      {
        label: 'Known Faces',
        data: trendData.known,
        borderColor: 'rgb(75, 192, 192)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        tension: 0.1,
      },
      {
        label: 'Unknown Faces',
        data: trendData.unknown,
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.2)',
        tension: 0.1,
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
      borderWidth: 1,
    }],
  } : null;

  const personChartData = personData ? {
    labels: personData.labels,
    datasets: [{
      label: 'Recognition Count',
      data: personData.data,
      backgroundColor: 'rgba(54, 162, 235, 0.8)',
      borderColor: 'rgba(54, 162, 235, 1)',
      borderWidth: 1,
    }],
  } : null;

  const hourlyChartData = hourlyData ? {
    labels: hourlyData.labels,
    datasets: [{
      label: 'Face Detections',
      data: hourlyData.data,
      borderColor: 'rgb(153, 102, 255)',
      backgroundColor: 'rgba(153, 102, 255, 0.2)',
      tension: 0.1,
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
      borderWidth: 1,
    }],
  } : null;

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-loading">
          <div className="loading-spinner"></div>
          <p>Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="dashboard-error">
          <h3>Error Loading Dashboard</h3>
          <p>{error}</p>
          <button onClick={fetchAllAnalytics} className="retry-button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Face Recognition Analytics Dashboard</h2>
        <button onClick={fetchAllAnalytics} className="refresh-button">
          Refresh Data
        </button>
      </div>

      {/* Overview Cards */}
      {overviewData && (
        <div className="overview-cards">
          <div className="overview-card">
            <h3>Total Faces</h3>
            <div className="metric">{overviewData.total_faces.toLocaleString()}</div>
          </div>
          <div className="overview-card">
            <h3>Recognition Rate</h3>
            <div className="metric">{overviewData.recognition_rate}%</div>
          </div>
          <div className="overview-card">
            <h3>Unique Persons</h3>
            <div className="metric">{overviewData.unique_persons}</div>
          </div>
          <div className="overview-card">
            <h3>Avg Confidence</h3>
            <div className="metric">{overviewData.avg_confidence.toFixed(3)}</div>
          </div>
        </div>
      )}

      {/* Charts Grid */}
      <div className="charts-grid">
        {/* Face Detection Trend */}
        <div className="chart-container">
          <h3>Face Detection Trend (Last 7 Days)</h3>
          {trendChartData ? (
            <div className="chart-wrapper">
              <Line data={trendChartData} options={chartOptions} />
            </div>
          ) : (
            <div className="no-data">No trend data available</div>
          )}
        </div>

        {/* Confidence Distribution */}
        <div className="chart-container">
          <h3>Confidence Score Distribution</h3>
          {confidenceChartData ? (
            <div className="chart-wrapper">
              <Bar data={confidenceChartData} options={chartOptions} />
            </div>
          ) : (
            <div className="no-data">No confidence data available</div>
          )}
        </div>

        {/* Person Frequency */}
        <div className="chart-container">
          <h3>Most Recognized Persons</h3>
          {personChartData ? (
            <div className="chart-wrapper">
              <Bar data={personChartData} options={chartOptions} />
            </div>
          ) : (
            <div className="no-data">No person data available</div>
          )}
        </div>

        {/* Hourly Activity */}
        <div className="chart-container">
          <h3>Hourly Activity Pattern</h3>
          {hourlyChartData ? (
            <div className="chart-wrapper">
              <Line data={hourlyChartData} options={chartOptions} />
            </div>
          ) : (
            <div className="no-data">No hourly data available</div>
          )}
        </div>

        {/* Camera Activity */}
        <div className="chart-container">
          <h3>Camera Activity Distribution</h3>
          {cameraChartData ? (
            <div className="chart-wrapper">
              <Pie data={cameraChartData} options={chartOptions} />
            </div>
          ) : (
            <div className="no-data">No camera data available</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;