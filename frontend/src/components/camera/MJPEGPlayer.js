import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import './MJPEGPlayer.css';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const MJPEGPlayer = ({ camera, onPlay, onError }) => {
  const [streamUrl, setStreamUrl] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [streamId, setStreamId] = useState(null);
  const imgRef = useRef(null);
  const retryTimeoutRef = useRef(null);
  const refreshIntervalRef = useRef(null);
  const frameTimeoutRef = useRef(null);
  const [retryCount, setRetryCount] = useState(0);
  const [frameCount, setFrameCount] = useState(0);
  const maxRetries = 3;
  const isStartingRef = useRef(false);
  const lastLoadTimeRef = useRef(null);
  const isMountedRef = useRef(true);

  // Generate stream ID from camera info
  const generateStreamId = (camera) => {
    if (camera.ip) {
      // Try to extract collection name from camera name or use a default
      let collectionName = 'default';

      if (camera.name && camera.name.includes('(')) {
        // Extract collection name from camera name format "CollectionName (IP)"
        collectionName = camera.name.split('(')[0].trim();
      } else if (camera.collectionId) {
        collectionName = camera.collectionId;
      }

      return `${collectionName}_${camera.ip}`;
    }
    return `camera_${camera.id}_${Date.now()}`;
  };

  // Start MJPEG stream
  const startStream = async () => {
    // Prevent multiple simultaneous requests
    if (isStartingRef.current) {
      console.log(`Stream already starting, skipping...`);
      return;
    }

    const newStreamId = generateStreamId(camera);

    // Check if stream already exists and is working
    if (streamId === newStreamId && streamUrl && !hasError) {
      console.log(`Stream ${newStreamId} already exists and working, reusing...`);
      setIsLoading(false);
      return;
    }

    try {
      isStartingRef.current = true;
      setIsLoading(true);
      setHasError(false);
      setStreamId(newStreamId);

      console.log(`Starting MJPEG stream for camera ${camera.name} (ID: ${camera.id})`);
      console.log('Camera object:', camera);
      console.log('Camera object:', camera);
      console.log('Camera object:', camera);

      // Start the stream using the camera ID
      const response = await axios.post(`${API_BASE_URL}/api/collections/cameras/${camera.id}/start-stream`, {}, {
        timeout: 10000 // 10 second timeout
      });

      if (response.data.success) {
        const baseUrl = `${API_BASE_URL}/api/collections/cameras/${camera.id}/frame`;
        const feedUrl = `${baseUrl}?t=${Date.now()}`;
        
        console.log('Setting up MJPEG frame from:', feedUrl);
        setStreamUrl(feedUrl);
        setStreamId(response.data.stream_id);
        setRetryCount(0);
        
        console.log(`MJPEG frame endpoint configured for camera ${camera.id}`);
      } else {
        throw new Error(response.data.message || 'Failed to start stream');
      }

    } catch (error) {
      console.error('Error starting MJPEG stream:', error);
      setHasError(true);
      setIsLoading(false);

      if (onError) {
        onError(error.response?.data?.detail || error.message);
      }

      // Retry logic with exponential backoff
      if (retryCount < maxRetries) {
        const backoffTime = Math.min(3000 * Math.pow(2, retryCount), 15000); // Max 15 seconds
        console.log(`Retrying stream start (${retryCount + 1}/${maxRetries}) in ${backoffTime/1000} seconds...`);
        retryTimeoutRef.current = setTimeout(() => {
          setRetryCount(prev => prev + 1);
          startStream();
        }, backoffTime);
      }
    } finally {
      isStartingRef.current = false;
    }
  };

  // Simplified and reliable frame refresh mechanism
  const startFrameRefresh = useCallback((baseUrl) => {
    // Clear any existing refresh mechanisms
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
    if (frameTimeoutRef.current) {
      clearTimeout(frameTimeoutRef.current);
      frameTimeoutRef.current = null;
    }

    console.log('🎬 Starting continuous frame refresh for:', baseUrl);

    const refreshFrame = () => {
      if (!isMountedRef.current || hasError) {
        return;
      }

      const timestamp = Date.now();
      const frameUrl = `${baseUrl}?t=${timestamp}&frame=${frameCount}`;
      
      if (imgRef.current) {
        // Direct update - let browser handle the loading
        imgRef.current.src = frameUrl;
        setFrameCount(prev => prev + 1);
        lastLoadTimeRef.current = timestamp;
      }
      
      // Schedule next frame update
      frameTimeoutRef.current = setTimeout(refreshFrame, 100); // 10 FPS for smoother streaming
    };
    
    // Start the continuous refresh cycle
    refreshFrame();
  }, [camera.name, hasError, frameCount]);

  // Stop frame refresh
  const stopFrameRefresh = useCallback(() => {
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
      refreshIntervalRef.current = null;
    }
    if (frameTimeoutRef.current) {
      clearTimeout(frameTimeoutRef.current);
      frameTimeoutRef.current = null;
    }
    console.log('🛑 Stopped frame refresh for camera:', camera.name);
  }, [camera.name]);

  // Stop stream
  const stopStream = async () => {
    // Stop frame refresh
    stopFrameRefresh();
    
    if (camera.id) {
      try {
        await axios.delete(`${API_BASE_URL}/api/collections/cameras/${camera.id}/stop-stream`);
        console.log(`Stopped MJPEG stream for camera ${camera.id}`);
      } catch (error) {
        console.error('Error stopping stream:', error);
      }
    }

    setStreamUrl(null);
    setStreamId(null);
    setIsLoading(true);
    setHasError(false);

    // Clear retry timeout
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  };

  // Handle initial image load
  const handleImageLoad = useCallback(() => {
    if (!isMountedRef.current) return;
    
    console.log(`✅ MJPEG frame loaded for camera ${camera.name}`);
    setIsLoading(false);
    setHasError(false);
    setRetryCount(0);
    
    // Start continuous frame refresh immediately after first frame loads
    if (streamUrl && !frameTimeoutRef.current) {
      const baseUrl = streamUrl.split('?')[0];
      console.log('🔄 Starting frame refresh for:', baseUrl);
      startFrameRefresh(baseUrl);
    }

    if (onPlay) {
      onPlay();
    }
  }, [camera.name, streamUrl, startFrameRefresh, onPlay]);

  // Handle image error - simplified approach
  const handleImageError = useCallback((event) => {
    if (!isMountedRef.current) return;
    
    console.error(`❌ Frame error for camera ${camera.name}:`, event.target?.src);
    
    // Don't stop streaming for individual frame errors - let it continue
    const timeSinceLastLoad = lastLoadTimeRef.current ? Date.now() - lastLoadTimeRef.current : Infinity;
    
    // Only stop if we haven't had a successful frame in the last 15 seconds
    if (timeSinceLastLoad > 15000) {
      setHasError(true);
      setIsLoading(false);
      stopFrameRefresh();

      if (onError) {
        onError('Stream connection lost');
      }

      // Retry the entire stream setup after a delay
      if (retryCount < maxRetries) {
        console.log(`🔁 Retrying stream (${retryCount + 1}/${maxRetries}) in 5 seconds...`);
        retryTimeoutRef.current = setTimeout(() => {
          setRetryCount(prev => prev + 1);
          setHasError(false);
          setIsLoading(true);
          startStream();
        }, 5000);
      }
    } else {
      // Recent successful loads, just log the error and continue
      console.warn(`⚠️ Temporary frame error for camera ${camera.name}, continuing stream...`);
    }
  }, [camera.name, onError, retryCount, maxRetries, stopFrameRefresh, startStream]);

  // Initialize stream when component mounts or camera changes
  useEffect(() => {
    isMountedRef.current = true;
    setFrameCount(0);
    lastLoadTimeRef.current = null;

    const initializeStream = async () => {
      if (isMountedRef.current) {
        await startStream();
      }
    };

    initializeStream();

    // Cleanup function
    return () => {
      isMountedRef.current = false;
      stopStream();
    };
  }, [camera.id]);

  // Handle streamUrl changes with improved loading
  useEffect(() => {
    if (streamUrl && imgRef.current && isMountedRef.current) {
      console.log('StreamURL changed, initializing frame loading:', streamUrl);
      
      // Stop any existing refresh cycle
      stopFrameRefresh();
      
      // Load initial frame
      const initialFrameUrl = `${streamUrl}?t=${Date.now()}`;
      imgRef.current.src = initialFrameUrl;
      setIsLoading(true);
      setHasError(false);
    }
  }, [streamUrl, stopFrameRefresh]);

  // Enhanced cleanup on unmount
  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
      if (frameTimeoutRef.current) {
        clearTimeout(frameTimeoutRef.current);
      }
      stopFrameRefresh();
    };
  }, [stopFrameRefresh]);

  if (hasError && retryCount >= maxRetries) {
    return (
      <div className="mjpeg-error">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FF4444" strokeWidth="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>Stream unavailable</span>
        <button
          className="retry-button"
          onClick={() => {
            setRetryCount(0);
            startStream();
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="mjpeg-player">
      {streamUrl && (
        <img
          ref={imgRef}
          alt={`Camera ${camera.name}`}
          className="mjpeg-stream"
          onLoad={handleImageLoad}
          onError={handleImageError}
          style={{ 
            display: isLoading ? 'none' : 'block',
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain'
          }}
        />
      )}
      {isLoading && (
        <div className="mjpeg-loading">
          <div className="loading-spinner"></div>
          <span>Connecting to stream...</span>
          {frameCount > 0 && (
            <small>Frames loaded: {frameCount}</small>
          )}
          {retryCount > 0 && (
            <small>Retry {retryCount}/{maxRetries}</small>
          )}
        </div>
      )}
    </div>
  );
};

export default MJPEGPlayer;
