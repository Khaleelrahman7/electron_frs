import React, { useState } from 'react';
import './App.css';
import FaceGallery from './components/FaceGallery';
import EventsWidget from './components/EventsWidget';
import RegistrationWidget from './components/RegistrationWidget';
import VideoWidget from './components/VideoWidget';
import FaceMatching from './components/FaceMatching';
import { CameraProvider } from './components/camera/CameraManager';
import SimpleCameraManager from './components/camera/SimpleCameraManager';
import StreamViewer from './components/StreamViewer';

// Import SVG icons
import { ReactComponent as GalleryIcon } from './icon/gallery.svg';
import { ReactComponent as EventsIcon } from './icon/Events.svg';
import { ReactComponent as RegistrationIcon } from './icon/registration.svg';
import { ReactComponent as FaceMatchingIcon } from './icon/face_matching.svg';
import { ReactComponent as VideoIcon } from './icon/video_processing.svg';
import { ReactComponent as CameraIcon } from './icon/camera.svg';
import { ReactComponent as StreamViewerIcon } from './icon/stream_viewer.svg';

function App() {
  const [activeTab, setActiveTab] = useState('gallery');

  const tabs = [
    { id: 'gallery', label: 'Gallery', icon: <GalleryIcon /> },
    { id: 'events', label: 'Events', icon: <EventsIcon /> },
    { id: 'registration', label: 'Registration', icon: <RegistrationIcon /> },
    { id: 'matching', label: 'Face Matching', icon: <FaceMatchingIcon /> },
    { id: 'video', label: 'Video Processing', icon: <VideoIcon /> },
    { id: 'camera', label: 'Camera Management', icon: <CameraIcon /> },
    { id: 'stream-viewer', label: 'Stream Viewer', icon: <StreamViewerIcon /> },
  ];

  const renderActiveComponent = () => {
    switch (activeTab) {
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
        return <FaceGallery />;
    }
  };

  return (
    <div className="app">
      <div className="app-layout">
        <aside className="sidebar">
          <div className="sidebar-header">
            <h1>🔍 Face Recognition System</h1>
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
