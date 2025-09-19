import React, { useState, useRef, useEffect } from 'react';

const WebRTCTest = () => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const animationRef = useRef(null);

  const startStream = async () => {
    try {
      console.log('Starting WebRTC test stream...');
      setError(null);
      
      // Create canvas
      const canvas = document.createElement('canvas');
      canvas.width = 640;
      canvas.height = 480;
      const ctx = canvas.getContext('2d');
      
      if (!ctx) {
        throw new Error('Failed to get canvas context');
      }

      canvasRef.current = canvas;

      // Create stream from canvas
      const stream = canvas.captureStream(30);
      console.log('Canvas stream created:', stream);

      // Assign to video element
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        console.log('Stream assigned to video');
        setIsStreaming(true);
      }

      // Start animation
      let frameCount = 0;
      const startTime = Date.now();

      const animate = () => {
        if (!isStreaming) return;

        // Clear canvas
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Add gradient
        const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
        gradient.addColorStop(0, '#ff0000');
        gradient.addColorStop(0.5, '#00ff00');
        gradient.addColorStop(1, '#0000ff');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Add text
        ctx.fillStyle = 'white';
        ctx.font = '24px Arial';
        ctx.fillText('WebRTC Test Stream', 50, 60);
        ctx.fillText(`Frame: ${frameCount}`, 50, 100);
        ctx.fillText(`Time: ${new Date().toLocaleTimeString()}`, 50, 140);

        // Add moving circle
        const elapsed = (Date.now() - startTime) / 1000;
        const x = 320 + 200 * Math.sin(elapsed);
        const y = 240 + 100 * Math.cos(elapsed);
        
        ctx.fillStyle = 'yellow';
        ctx.beginPath();
        ctx.arc(x, y, 20, 0, 2 * Math.PI);
        ctx.fill();

        frameCount++;
        animationRef.current = requestAnimationFrame(animate);
      };

      animate();
      console.log('Animation started');

    } catch (err) {
      console.error('Error starting stream:', err);
      setError(err.message);
    }
  };

  const stopStream = () => {
    console.log('Stopping stream...');
    setIsStreaming(false);
    
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
    
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject;
      const tracks = stream.getTracks();
      tracks.forEach(track => track.stop());
      videoRef.current.srcObject = null;
    }
    
    canvasRef.current = null;
  };

  useEffect(() => {
    return () => {
      stopStream();
    };
  }, []);

  return (
    <div style={{ padding: '20px', background: '#1a1a1a', color: 'white' }}>
      <h2>WebRTC Stream Test</h2>
      
      <div style={{ marginBottom: '20px' }}>
        <button 
          onClick={isStreaming ? stopStream : startStream}
          style={{
            padding: '10px 20px',
            background: isStreaming ? '#dc2626' : '#059669',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          {isStreaming ? 'Stop Stream' : 'Start Stream'}
        </button>
      </div>

      {error && (
        <div style={{ 
          background: '#dc2626', 
          padding: '10px', 
          borderRadius: '4px', 
          marginBottom: '20px' 
        }}>
          Error: {error}
        </div>
      )}

      <div style={{ 
        border: '2px solid #333', 
        borderRadius: '8px', 
        overflow: 'hidden',
        width: '640px',
        height: '480px',
        background: '#000'
      }}>
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          style={{
            width: '100%',
            height: '100%',
            objectFit: 'cover'
          }}
        />
      </div>

      <div style={{ marginTop: '10px', fontSize: '14px', opacity: 0.7 }}>
        Status: {isStreaming ? 'Streaming' : 'Stopped'}
      </div>
    </div>
  );
};

export default WebRTCTest;
