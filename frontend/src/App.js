import React, { useState } from 'react';
import './App.css';
import FaceGallery from './components/FaceGallery';
import EventsWidget from './components/EventsWidget';
import RegistrationWidget from './components/RegistrationWidget';
import VideoWidget from './components/VideoWidget';
import { CameraProvider } from './components/camera/CameraManager';
import SimpleCameraManager from './components/camera/SimpleCameraManager';
import WebRTCTest from './components/camera/WebRTCTest';

function App() {
  const [activeTab, setActiveTab] = useState('gallery');

  const tabs = [
    { id: 'gallery', label: 'Gallery', icon: '👥' },
    { id: 'events', label: 'Events', icon: '📅' },
    { id: 'registration', label: 'Registration', icon: '➕' },
    { id: 'video', label: 'Video Processing', icon: '🎥' },
    { id: 'camera', label: 'Camera Management', icon: '📹' },
    { id: 'webrtc-test', label: 'WebRTC Test', icon: '🔴' }
  ];

  const renderActiveComponent = () => {
    switch (activeTab) {
      case 'gallery':
        return <FaceGallery />;
      case 'events':
        return <EventsWidget />;
      case 'registration':
        return <RegistrationWidget />;
      case 'video':
        return <VideoWidget />;
      case 'camera':
        return (
          <CameraProvider>
            <SimpleCameraManager />
          </CameraProvider>
        );
      case 'webrtc-test':
        return <WebRTCTest />;
      default:
        return <FaceGallery />;
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>🔍 Face Recognition System</h1>
        <nav className="tab-navigation">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
              title={tab.label}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span className="tab-label">{tab.label}</span>
            </button>
          ))}
        </nav>
      </header>

      <main className="app-content">
        {renderActiveComponent()}
      </main>
    </div>
  );
}

export default App;
