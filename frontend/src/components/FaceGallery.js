import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import PersonCard from './PersonCard';
import './FaceGallery.css';

import { API_BASE_URL } from '../utils/apiConfig';
const GALLERY_ENDPOINT = `${API_BASE_URL}/api/registration/gallery`;

const FaceGallery = () => {
  const [galleryData, setGalleryData] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [columns, setColumns] = useState(4);

  console.log('FaceGallery component rendering, galleryData:', galleryData);

  const calculateColumns = useCallback(() => {
    const containerWidth = window.innerWidth - 80; // Account for margins
    const minCardWidth = 250;
    const spacing = 20;
    const maxCols = Math.max(1, Math.floor((containerWidth + spacing) / (minCardWidth + spacing)));
    return Math.min(maxCols, 5);
  }, []);

  const loadGallery = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Loading gallery from:', GALLERY_ENDPOINT);
      const response = await axios.get(GALLERY_ENDPOINT, {
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      console.log('Gallery response:', response.data);
      setGalleryData(response.data);
    } catch (err) {
      console.error('Gallery loading error:', err);
      let errorMessage = 'Failed to load gallery data';
      
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Request timed out. Please check if the backend server is running.';
      } else if (err.response) {
        errorMessage = `Server error: ${err.response.status} - ${err.response.data?.detail || err.response.statusText}`;
      } else if (err.request) {
        errorMessage = `Cannot connect to backend server. Please ensure the server is running on ${API_BASE_URL}`;
      } else {
        errorMessage = `Error: ${err.message}`;
      }
      
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    console.log('FaceGallery useEffect triggered, calling loadGallery');
    loadGallery();
  }, [loadGallery]);

  useEffect(() => {
    const handleResize = () => {
      setColumns(calculateColumns());
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [calculateColumns]);

  if (loading) {
    return (
      <div className="gallery-container">
        <div className="loading">Loading gallery...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="gallery-container">
        <div className="error">{error}</div>
        <button onClick={loadGallery} className="refresh-btn">
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className="gallery-container">
      <div className="gallery-controls">
        <button onClick={loadGallery} className="refresh-btn">
          Refresh Gallery
        </button>
        <div style={{ marginLeft: '10px', fontSize: '0.9rem', color: '#666' }}>
          Status: {loading ? 'Loading...' : error ? 'Error' : `${Object.keys(galleryData).length} faces loaded`}
        </div>
      </div>

      <div
        className="gallery-grid"
        style={{
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
          gap: '20px'
        }}
      >
        {Object.entries(galleryData).map(([personId, personData]) => {
          // Use the image filename from backend, fallback to original.jpg
          const imageFilename = personData.image_filename || 'original.jpg';

          return (
            <PersonCard
              key={personId}
              name={personData.name}
              photoPath={`${API_BASE_URL}/api/gallery/image/${personId}/${imageFilename}`}
              details={{
                age: personData.age,
                gender: personData.gender,
                category: personData.category
              }}
            />
          );
        })}
      </div>

      {Object.keys(galleryData).length === 0 && !loading && !error && (
        <div className="empty-state">
          No faces found in gallery. Click "Refresh Gallery" to load data.
        </div>
      )}
    </div>
  );
};

export default FaceGallery;
