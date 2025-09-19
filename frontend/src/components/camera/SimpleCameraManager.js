import React, { useState } from 'react';
import { useCameras } from './CameraManager';
import TabbedCameraManager from './TabbedCameraManager';
import CollectionManager from './CollectionManager';
import { Settings, Grid } from 'lucide-react';
import './SimpleCameraManager.css';

const SimpleCameraManager = () => {
  const [viewMode, setViewMode] = useState('tabbed'); // 'tabbed' or 'classic'
  const [showManager, setShowManager] = useState(false);

  if (!showManager) {
    return (
      <div className="simple-camera-manager">
        <div className="welcome-screen">
          <div className="welcome-content">
            <div className="welcome-header">
              <Grid size={48} />
              <h1>Camera Management System</h1>
              <p>Manage your cameras, collections, and live streams</p>
            </div>
            
            <div className="welcome-actions">
              <button 
                className="primary-action-btn"
                onClick={() => {
                  setViewMode('tabbed');
                  setShowManager(true);
                }}
              >
                <Grid size={20} />
                Open Tabbed Manager
              </button>
              
              <button 
                className="secondary-action-btn"
                onClick={() => {
                  setViewMode('classic');
                  setShowManager(true);
                }}
              >
                <Settings size={20} />
                Open Classic Manager
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="simple-camera-manager">
      {viewMode === 'tabbed' ? (
        <TabbedCameraManager 
          onClose={() => setShowManager(false)}
        />
      ) : (
        <div className="classic-manager-wrapper">
          <div className="classic-header">
            <h1>Classic Camera Manager</h1>
            <div className="header-actions">
              <button 
                className="switch-view-btn"
                onClick={() => setViewMode('tabbed')}
              >
                <Grid size={16} />
                Switch to Tabbed View
              </button>
              <button 
                className="close-btn"
                onClick={() => setShowManager(false)}
              >
                ✕
              </button>
            </div>
          </div>
          <CollectionManager 
            onClose={() => setShowManager(false)}
          />
        </div>
      )}
    </div>
  );
};

export default SimpleCameraManager;
