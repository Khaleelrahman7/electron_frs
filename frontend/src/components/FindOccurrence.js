import React, { useState } from 'react';
import axios from 'axios';
import FaceCard from './FaceCard';
import './FindOccurrence.css';

const API_BASE_URL = "http://localhost:8000/api/events";

const FindOccurrence = () => {
  const [selectedImage, setSelectedImage] = useState(null);
  const [selectedImagePath, setSelectedImagePath] = useState('');
  const [matchingFaces, setMatchingFaces] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleImageSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setSelectedImage(file);
      setSelectedImagePath(URL.createObjectURL(file));
      setMatchingFaces([]);
      setError(null);
    }
  };

  const findMatches = async (retryCount = 0) => {
    if (!selectedImage) {
      setError('Please select an image first.');
      return;
    }

    setLoading(true);
    setError(null);
    setMatchingFaces([]);

    try {
      const formData = new FormData();
      formData.append('image', selectedImage);

      console.log('Finding matches for image:', selectedImage.name);
      setError('Processing image... This may take up to 2 minutes for large datasets.');

      const response = await axios.post(`${API_BASE_URL}/match-face`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 120000, // 2 minutes
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setError(`Uploading image... ${percentCompleted}%`);
        }
      });

      console.log('Match response:', response.data);
      setMatchingFaces(response.data);
      setError(null);
    } catch (err) {
      console.error('Find matches error:', err);
      let errorMessage = 'Failed to find matches';

      if (err.code === 'ECONNABORTED') {
        if (retryCount < 2) {
          setError(`Request timed out. Retrying... (${retryCount + 1}/3)`);
          setTimeout(() => findMatches(retryCount + 1), 2000);
          return;
        } else {
          errorMessage = 'Request timed out after multiple attempts. The dataset might be very large. Please try with a smaller image or contact support.';
        }
      } else if (err.response?.status === 400) {
        errorMessage = err.response.data.detail || 'Invalid image or no face detected';
      } else if (err.response?.status === 500) {
        errorMessage = 'Server error occurred. Please try again or contact support if the problem persists.';
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
  };

  return (
    <div className="find-occurrence">
      <div className="image-selection">
        <div className="selected-image-container">
          {selectedImagePath ? (
            <img 
              src={selectedImagePath} 
              alt="Selected" 
              className="selected-image"
            />
          ) : (
            <div className="no-image-placeholder">
              No image selected
            </div>
          )}
        </div>
        
        <div className="controls">
          <input
            type="file"
            accept="image/*"
            onChange={handleImageSelect}
            className="file-input"
            id="image-input"
          />
          <label htmlFor="image-input" className="select-btn">
            Select Image
          </label>
          
          <button 
            onClick={findMatches} 
            disabled={!selectedImage || loading}
            className="find-btn"
          >
            {loading ? 'Searching...' : 'Find Matches'}
          </button>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="results-container">
        {loading ? (
          <div className="loading">Searching for matches...</div>
        ) : matchingFaces.length > 0 ? (
          <div className="results-grid">
            {matchingFaces.map((match, index) => (
              <FaceCard
                key={`match-${index}`}
                imagePath={match.image_path}
                name={`${match.name} (${(match.confidence * 100).toFixed(1)}%)`}
                camera=""
                timestamp={match.timestamp}
              />
            ))}
          </div>
        ) : selectedImage && !loading ? (
          <div className="empty-state">
            No matching faces found
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default FindOccurrence;
