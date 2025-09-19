import React, { useState, useEffect } from 'react';
import { useCameras } from './CameraManager';
import { Camera, Plus, Settings, List, X } from 'lucide-react';
import AddCameraForm from './AddCameraForm';
import CameraCard from './CameraCard';
import './TabbedCameraManager.css';

const TabbedCameraManager = ({ onClose }) => {
  const {
    collections,
    cameras,
    createCollection,
    renameCollection,
    deleteCollection,
    addCameraToCollection,
    removeCameraFromCollection,
    getCamerasByCollection,
    activeCollection,
    setCollectionActive,
    activateCamera,
    deactivateCamera,
    initialize,
    loading,
    error
  } = useCameras();

  const [activeTab, setActiveTab] = useState('cameras');
  const [selectedCollection, setSelectedCollection] = useState('default');

  // Update selected collection when collections are loaded
  useEffect(() => {
    if (collections && collections.length > 0) {
      // Check if the current selectedCollection exists in the loaded collections
      const collectionExists = collections.some(c => c.id === selectedCollection);
      if (!collectionExists && selectedCollection !== 'all') {
        // If default collection doesn't exist, set to 'all' or first available collection
        const defaultCollection = collections.find(c => c.id === 'default');
        if (defaultCollection) {
          setSelectedCollection('default');
        } else {
          setSelectedCollection('all');
        }
      }
    }
  }, [collections, selectedCollection]);
  const [showAddCameraForm, setShowAddCameraForm] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [showCreateCollection, setShowCreateCollection] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState('');

  useEffect(() => {
    initialize();
  }, [initialize]);

  const tabs = [
    { id: 'cameras', label: 'Camera List', icon: List },
    { id: 'add', label: 'Add Camera', icon: Plus },
    { id: 'settings', label: 'Settings', icon: Settings }
  ];

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    if (tabId === 'add') {
      setShowAddCameraForm(true);
      setEditingCamera(null);
    } else {
      setShowAddCameraForm(false);
    }
  };

  const handleAddCamera = () => {
    setActiveTab('add');
    setShowAddCameraForm(true);
    setEditingCamera(null);
  };

  const handleEditCamera = (camera) => {
    setActiveTab('add');
    setEditingCamera(camera);
    setShowAddCameraForm(true);
  };

  const handleCloseCameraForm = () => {
    setShowAddCameraForm(false);
    setEditingCamera(null);
    setActiveTab('cameras');
  };

  const handleCreateCollection = async (e) => {
    e.preventDefault();
    if (newCollectionName.trim()) {
      try {
        await createCollection(newCollectionName.trim());
        setNewCollectionName('');
        setShowCreateCollection(false);
      } catch (error) {
        console.error('Error creating collection:', error);
      }
    }
  };

  const handleActivateCamera = async (cameraId) => {
    try {
      console.log('Activating camera:', cameraId);
      const result = await activateCamera(cameraId);
      console.log('Camera activation result:', result);

      // Refresh the camera list to show updated status
      await initialize();

      // Also refresh camera streams for the Live view
      // This will help the Live view pick up the newly activated camera
      setTimeout(() => {
        // Trigger a refresh of camera streams after a short delay
        // to allow the backend to process the activation
        window.dispatchEvent(new CustomEvent('refreshCameraStreams'));
      }, 1000);

    } catch (error) {
      console.error('Error activating camera:', error);
    }
  };

  const handleDeactivateCamera = async (cameraId) => {
    try {
      console.log('Deactivating camera:', cameraId);
      const result = await deactivateCamera(cameraId);
      console.log('Camera deactivation result:', result);

      // Refresh the camera list to show updated status
      await initialize();
    } catch (error) {
      console.error('Error deactivating camera:', error);
    }
  };

  const currentCameras = selectedCollection === 'all'
    ? cameras
    : getCamerasByCollection(selectedCollection);



  const activeCameras = currentCameras?.filter(camera => camera.is_active) || [];

  if (loading) {
    return (
      <div className="tabbed-camera-manager loading">
        <div className="loading-spinner">
          <Camera size={48} />
          <p>Loading camera management...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tabbed-camera-manager">
      {/* Header */}
      <div className="manager-header">
        <div className="header-title">
          <Camera size={24} />
          <h2>Camera Management</h2>
        </div>
        <button className="close-button" onClick={onClose}>
          ✕
        </button>
      </div>

      {/* Collection Selector */}
      <div className="collection-selector">
        <label htmlFor="collection-select">Collection:</label>
        <select
          id="collection-select"
          value={selectedCollection}
          onChange={(e) => setSelectedCollection(e.target.value)}
          className="collection-dropdown"
        >
          <option value="all">All Collections</option>
          {collections?.map(collection => (
            <option key={collection.id} value={collection.id}>
              {collection.name} ({collection.camera_count || 0} cameras)
            </option>
          ))}
        </select>
        <button
          className="create-collection-btn"
          onClick={() => setShowCreateCollection(true)}
        >
          <Plus size={16} />
          New Collection
        </button>
      </div>

      {/* Create Collection Modal */}
      {showCreateCollection && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>Create New Collection</h3>
            <form onSubmit={handleCreateCollection}>
              <input
                type="text"
                value={newCollectionName}
                onChange={(e) => setNewCollectionName(e.target.value)}
                placeholder="Enter collection name"
                autoFocus
                required
              />
              <div className="modal-actions">
                <button type="submit" className="primary-btn">Create</button>
                <button 
                  type="button" 
                  className="secondary-btn"
                  onClick={() => setShowCreateCollection(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="tab-navigation">
        {tabs.map(tab => {
          const IconComponent = tab.icon;
          return (
            <button
              key={tab.id}
              className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => handleTabChange(tab.id)}
            >
              <IconComponent size={18} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {error && (
          <div className="error-banner">
            <p>Error: {error}</p>
          </div>
        )}

        {/* Camera List Tab */}
        {activeTab === 'cameras' && (
          <div className="cameras-tab">
            <div className="tab-header">
              <h3>
                Cameras in {selectedCollection === 'all' ? 'All Collections' :
                  collections?.find(c => c.id === selectedCollection)?.name || 'Unknown Collection'}
              </h3>
              <div className="camera-stats">
                <span className="stat">
                  Total: {currentCameras?.length || 0}
                </span>
                <span className="stat active">
                  Active: {activeCameras.length}
                </span>
              </div>
              <button className="add-camera-btn" onClick={handleAddCamera}>
                <Plus size={16} />
                Add Camera
              </button>
            </div>

            <div className="cameras-list">
              {currentCameras?.length === 0 ? (
                <div className="empty-state">
                  <Camera size={64} />
                  <h3>No cameras found</h3>
                  <p>Add your first camera to get started</p>
                  <button className="primary-btn" onClick={handleAddCamera}>
                    <Plus size={16} />
                    Add Camera
                  </button>
                </div>
              ) : (
                <div className="camera-table">
                  <div className="table-header">
                    <div className="col-name">Camera Name</div>
                    <div className="col-location">Location</div>
                    <div className="col-ip">IP Address</div>
                    <div className="col-status">Status</div>
                    <div className="col-actions">Actions</div>
                  </div>
                  {currentCameras?.map(camera => (
                    <div key={camera.id} className="table-row">
                      <div className="col-name">
                        <div className="camera-name">{camera.name}</div>
                      </div>
                      <div className="col-location">{camera.location || 'Unknown'}</div>
                      <div className="col-ip">{camera.ip_address}</div>
                      <div className="col-status">
                        <span className={`status-badge ${camera.is_active ? 'active' : 'inactive'}`}>
                          {camera.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      <div className="col-actions">
                        <button
                          className="action-btn edit"
                          onClick={() => handleEditCamera(camera)}
                          title="Edit Camera"
                        >
                          Edit
                        </button>
                        <button
                          className="action-btn activate"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('Activate button clicked for camera:', camera.id, 'is_active:', camera.is_active);
                            if (camera.is_active) {
                              handleDeactivateCamera(camera.id);
                            } else {
                              handleActivateCamera(camera.id);
                            }
                          }}
                          title={camera.is_active ? 'Deactivate' : 'Activate'}
                        >
                          {camera.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}



        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="settings-tab">
            <div className="tab-header">
              <h3>Camera Settings</h3>
            </div>

            <div className="settings-content">
              <div className="settings-section">
                <h4>General Settings</h4>
                <div className="setting-item">
                  <label>Default Collection</label>
                  <select value={selectedCollection} onChange={(e) => setSelectedCollection(e.target.value)}>
                    <option value="all">All Collections</option>
                    {collections?.map(collection => (
                      <option key={collection.id} value={collection.id}>
                        {collection.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="setting-item">
                  <label>Auto-refresh interval</label>
                  <select defaultValue="30">
                    <option value="10">10 seconds</option>
                    <option value="30">30 seconds</option>
                    <option value="60">1 minute</option>
                    <option value="300">5 minutes</option>
                  </select>
                </div>
              </div>

              <div className="settings-section">
                <h4>Stream Settings</h4>
                <div className="setting-item">
                  <label>Default stream quality</label>
                  <select defaultValue="medium">
                    <option value="low">Low (480p)</option>
                    <option value="medium">Medium (720p)</option>
                    <option value="high">High (1080p)</option>
                  </select>
                </div>
                <div className="setting-item">
                  <label>
                    <input type="checkbox" defaultChecked />
                    Enable motion detection
                  </label>
                </div>
              </div>

              <div className="settings-section">
                <h4>Notifications</h4>
                <div className="setting-item">
                  <label>
                    <input type="checkbox" defaultChecked />
                    Camera offline alerts
                  </label>
                </div>
                <div className="setting-item">
                  <label>
                    <input type="checkbox" />
                    Motion detection alerts
                  </label>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Add Camera Tab */}
        {activeTab === 'add' && (
          <div className="add-camera-tab">
            <div className="tab-header">
              <h3>{editingCamera ? 'Edit Camera' : 'Add New Camera'}</h3>
            </div>
            <div className="form-container">
              <AddCameraForm
                collectionId={selectedCollection !== 'all' ? selectedCollection : null}
                onClose={handleCloseCameraForm}
                editingCamera={editingCamera}
              />
            </div>
          </div>
        )}



        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div className="settings-tab">
            <div className="tab-header">
              <h3>Camera Settings</h3>
            </div>
            <div className="settings-content">
              <div className="setting-group">
                <h4>Collections</h4>
                <div className="collections-list">
                  {collections?.map(collection => (
                    <div key={collection.id} className="collection-item">
                      <div className="collection-info">
                        <span className="collection-name">{collection.name}</span>
                        <span className="collection-count">
                          {collection.camera_count || 0} cameras
                        </span>
                      </div>
                      <div className="collection-actions">
                        <button className="edit-btn">Edit</button>
                        {collection.id !== 'default' && (
                          <button 
                            className="delete-btn"
                            onClick={() => deleteCollection(collection.id)}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TabbedCameraManager;
