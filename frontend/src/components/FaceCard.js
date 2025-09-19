import React, { useState, useEffect } from 'react';
import './FaceCard.css';

const FaceCard = ({ imagePath, name, camera, timestamp }) => {
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  const handleImageError = () => {
    console.error('Failed to load image:', imagePath);
    setImageError(true);
  };

  const handleImageLoad = () => {
    console.log('Image loaded successfully:', imagePath);
    setImageLoaded(true);
  };

  // Reset image states when imagePath changes
  useEffect(() => {
    setImageError(false);
    setImageLoaded(false);
  }, [imagePath]);

  // Format timestamp for display
  const formatTimestamp = (timestamp) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch (error) {
      return timestamp;
    }
  };

  return (
    <div className="face-card">
      <div className="image-container">
        {!imageError ? (
          <img
            src={imagePath}
            alt={name}
            className={`face-image ${imageLoaded ? 'loaded' : ''}`}
            onError={handleImageError}
            onLoad={handleImageLoad}
          />
        ) : (
          <div className="no-image">
            <span>No Image Available</span>
            <small>{imagePath}</small>
          </div>
        )}
      </div>
      
      <div className="face-info">
        <h4 className="face-name">{name}</h4>
        {camera && <p className="face-camera">Camera: {camera}</p>}
        {timestamp && <p className="face-timestamp">{formatTimestamp(timestamp)}</p>}
      </div>
    </div>
  );
};

export default FaceCard;
