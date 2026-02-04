import React, { useState, useEffect } from 'react';
import './App.css';
import FaceGallery from './components/FaceGallery';
import EventsWidget from './components/EventsWidget';
import RegistrationWidget from './components/RegistrationWidget';
import VideoWidget from './components/VideoWidget';
import FaceMatching from './components/FaceMatching';
import Dashboard from './components/dashboard/Dashboard';
import { CameraProvider } from './components/camera/CameraManager';
import SimpleCameraManager from './components/camera/SimpleCameraManager';
import StreamViewer from './components/StreamViewer';
import { detectBackendUrl, API_BASE_URL } from './utils/apiConfig';

// Import SVG icons
import { ReactComponent as GalleryIcon } from './icon/gallery.svg';
import { ReactComponent as EventsIcon } from './icon/Events.svg';
import { ReactComponent as RegistrationIcon } from './icon/registration.svg';
import { ReactComponent as FaceMatchingIcon } from './icon/face_matching.svg';
import { ReactComponent as VideoIcon } from './icon/video_processing.svg';
import { ReactComponent as CameraIcon } from './icon/camera.svg';
import { ReactComponent as StreamViewerIcon } from './icon/stream_viewer.svg';
import { ReactComponent as DashboardIcon } from './icon/dashboard.svg';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isCheckingBackend, setIsCheckingBackend] = useState(true);

  useEffect(() => {
    // Auto-detect backend URL and switch if necessary
    const checkBackend = async () => {
      try {
        const workingUrl = await detectBackendUrl();
        const currentUrl = localStorage.getItem('api_base_url');
        
        // If we found a working URL
        if (workingUrl) {
          // If it's different from what we have saved (or we have nothing saved)
          // AND it's different from the current runtime default (to avoid unnecessary reloads if default matches)
          if (workingUrl !== currentUrl && workingUrl !== API_BASE_URL) {
            console.log(`Switching API URL to ${workingUrl}`);
            localStorage.setItem('api_base_url', workingUrl);
            window.location.reload();
            return;
          }
        } else {
          // If no server found, and we have a stored URL that might be dead
          if (currentUrl) {
            console.warn(`Stored backend URL ${currentUrl} is not responding. Resetting to defaults.`);
            localStorage.removeItem('api_base_url');
            window.location.reload();
            return;
          }
          
          console.warn('No backend server detected.');
        }
      } catch (error) {
        console.error('Backend detection failed:', error);
      } finally {
        setIsCheckingBackend(false);
      }
    };
    
    checkBackend();
  }, []);

  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: <DashboardIcon /> },
    { id: 'registration', label: 'Registration', icon: <RegistrationIcon /> },
    { id: 'gallery', label: 'Gallery', icon: <GalleryIcon /> },
    { id: 'events', label: 'Events', icon: <EventsIcon /> },
    { id: 'matching', label: 'Face Matching', icon: <FaceMatchingIcon /> },
    { id: 'video', label: 'Video Processing', icon: <VideoIcon /> },
    { id: 'camera', label: 'Camera Management', icon: <CameraIcon /> },
    { id: 'stream-viewer', label: 'Stream Viewer', icon: <StreamViewerIcon /> },
  ];

  const renderActiveComponent = () => {
    if (isCheckingBackend) {
      return (
        <div className="loading-screen">
          <div className="loading-spinner"></div>
          <h2>Connecting to Server...</h2>
          <p>Checking available connection points...</p>
        </div>
      );
    }

    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'gallery':
        return <FaceGallery />;
      case 'events':
        return <EventsWidget />;
      case 'registration':
        return <RegistrationWidget />;
      case 'matching':
        return <FaceMatching />;
      case 'video':
        return <VideoWidget />;
      case 'camera':
        return (
          <CameraProvider>
            <SimpleCameraManager />
          </CameraProvider>
        );
      case 'stream-viewer':
        return <StreamViewer />;
      case 'webrtc-test':
        return <WebRTCTest />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="app">
      <div className="app-layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <h1>Face Recognition System</h1>
          </div>
          <nav className="sidebar-navigation">
            {tabs.map(tab => (
              <button
                key={tab.id}
                className={`sidebar-button ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
                title={tab.label}
              >
                <span className="sidebar-icon">{tab.icon}</span>
                <span className="sidebar-label">{tab.label}</span>
              </button>
            ))}
          </nav>
        </aside>

        <main className="main-content">
          {renderActiveComponent()}
        </main>
      </div>
    </div>
  );
}

export default App;
