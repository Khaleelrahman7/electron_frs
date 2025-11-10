import React, { useState, useRef } from 'react';
import './RegistrationWidget.css';

import { API_BASE_URL as BASE_URL } from '../utils/apiConfig';

const RegistrationWidget = () => {
  const [activeMode, setActiveMode] = useState('single');
  const [formData, setFormData] = useState({
    name: '',
    age: '',
    gender: 'Male',
    category: ''
  });
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState(''); // 'success' or 'error'
  const fileInputRef = useRef(null);

  // Bulk registration with Excel + Folder
  const [excelFile, setExcelFile] = useState(null);
  const [selectedFolder, setSelectedFolder] = useState('');
  const excelFileInputRef = useRef(null);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const selectImage = (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        showMessage('Please select a valid image file', 'error');
        return;
      }

      setImageFile(file);
      
      const reader = new FileReader();
      reader.onload = (e) => {
        setImagePreview(e.target.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const showMessage = (text, type) => {
    setMessage(text);
    setMessageType(type);
    setTimeout(() => {
      setMessage('');
      setMessageType('');
    }, 5000);
  };

  const resetForm = () => {
    setFormData({
      name: '',
      age: '',
      gender: 'Male',
      category: ''
    });
    setImageFile(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const registerSingle = async () => {
    // Validation
    if (!imageFile) {
      showMessage('Please select an image first', 'error');
      return;
    }

    if (!formData.name.trim()) {
      showMessage('Please enter a name', 'error');
      return;
    }

    setIsLoading(true);
    setMessage('Registering person...');

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('image', imageFile);
      formDataToSend.append('name', formData.name.trim());
      formDataToSend.append('age', formData.age || '');
      formDataToSend.append('gender', formData.gender);
      formDataToSend.append('category', formData.category.trim());

      const response = await fetch(`${BASE_URL}/api/registration/register/single`, {
        method: 'POST',
        body: formDataToSend,
      });

      const result = await response.json();

      if (response.ok && result.status === 'success') {
        showMessage(`Successfully registered ${formData.name}!`, 'success');
        resetForm();
      } else {
        // FastAPI returns error messages in the 'detail' field for HTTPException
        const errorMessage = result.detail || result.message || 'Registration failed';
        showMessage(errorMessage, 'error');
      }
    } catch (error) {
      console.error('Registration error:', error);
      showMessage('Failed to connect to server. Please ensure the backend is running.', 'error');
    } finally {
      setIsLoading(false);
    }
  };



  const handleExcelFileSelect = (event) => {
    const file = event.target.files[0];
    if (file) {
      setExcelFile(file);
      showMessage(`Excel file selected: ${file.name}`, 'success');
    }
  };

  const handleFolderSelect = async () => {
    try {
      const result = await window.electronAPI.selectFolder();
      if (result.success && result.folderPath) {
        setSelectedFolder(result.folderPath);
        showMessage(`Folder selected: ${result.folderPath}`, 'success');
      }
    } catch (error) {
      console.error('Error selecting folder:', error);
      showMessage('Failed to select folder', 'error');
    }
  };

  const handleBulkRegistration = async () => {
    if (!excelFile) {
      showMessage('Please select an Excel file first', 'error');
      return;
    }

    if (!selectedFolder) {
      showMessage('Please select a data folder first', 'error');
      return;
    }

    setIsLoading(true);
    setMessage('Processing bulk registration...');

    try {
      const formData = new FormData();
      formData.append('excel_file', excelFile);
      formData.append('data_dir', selectedFolder);

      const response = await fetch(`${BASE_URL}/api/registration/register/bulk`, {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (response.ok) {
        const successCount = result.filter(r => r.status === 'success').length;
        const totalCount = result.length;
        showMessage(`Bulk registration completed: ${successCount}/${totalCount} successful`, 'success');

        // Reset form
        setExcelFile(null);
        setSelectedFolder('');
        if (excelFileInputRef.current) {
          excelFileInputRef.current.value = '';
        }
      } else {
        const errorMessage = result.detail || 'Bulk registration failed';
        showMessage(errorMessage, 'error');
      }
    } catch (error) {
      console.error('Bulk registration error:', error);
      showMessage('Failed to connect to server. Please ensure the backend is running.', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="registration-widget">
      <div className="registration-header">
        <h2>Person Registration</h2>
        <div className="mode-selector">
          <button
            className={`mode-btn ${activeMode === 'single' ? 'active' : ''}`}
            onClick={() => setActiveMode('single')}
          >
            Single Registration
          </button>
          <button
            className={`mode-btn ${activeMode === 'bulk' ? 'active' : ''}`}
            onClick={() => setActiveMode('bulk')}
          >
            Bulk Registration
          </button>
        </div>
      </div>

      {message && (
        <div className={`message ${messageType}`}>
          {message}
        </div>
      )}

      {activeMode === 'single' && (
        <div className="single-registration">
          <div className="registration-form">
            <div className="form-section">
              <h3>Person Information</h3>
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  placeholder="Enter person's name"
                  disabled={isLoading}
                />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Age</label>
                  <input
                    type="number"
                    value={formData.age}
                    onChange={(e) => handleInputChange('age', e.target.value)}
                    placeholder="Age"
                    min="1"
                    max="120"
                    disabled={isLoading}
                  />
                </div>
                <div className="form-group">
                  <label>Gender</label>
                  <select
                    value={formData.gender}
                    onChange={(e) => handleInputChange('gender', e.target.value)}
                    disabled={isLoading}
                  >
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>
              <div className="form-group">
                <label>Category</label>
                <input
                  type="text"
                  value={formData.category}
                  onChange={(e) => handleInputChange('category', e.target.value)}
                  placeholder="e.g., Employee, Visitor, Student"
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="form-section">
              <h3>Photo Upload</h3>
              <div
                className="image-upload-area"
                onClick={() => {
                  console.log('Image upload area clicked');
                  if (!isLoading) fileInputRef.current?.click();
                }}
                style={{ cursor: isLoading ? 'not-allowed' : 'pointer' }}
              >
                {imagePreview ? (
                  <div className="image-preview">
                    <img src={imagePreview} alt="Preview" />
                    <button
                      type="button"
                      className="remove-image"
                      onClick={(e) => {
                        e.stopPropagation();
                        setImageFile(null);
                        setImagePreview(null);
                        if (fileInputRef.current) fileInputRef.current.value = '';
                      }}
                      disabled={isLoading}
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="upload-placeholder">
                    <div className="upload-icon">📷</div>
                    <p>Click to select an image</p>
                    <small>Supported: JPG, PNG, JPEG</small>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={selectImage}
                  style={{ display: 'none' }}
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="btn-secondary"
                onClick={resetForm}
                disabled={isLoading}
              >
                Reset
              </button>
              <button
                type="button"
                className="btn-primary"
                onClick={registerSingle}
                disabled={isLoading || !imageFile || !formData.name.trim()}
              >
                {isLoading ? 'Registering...' : 'Register Person'}
              </button>
            </div>
          </div>
        </div>
      )}

      {activeMode === 'bulk' && (
        <div className="excel-bulk-registration">
          <div className="bulk-info">
            <h3>Bulk Registration</h3>
            <p>Register multiple people using an Excel file with person data and a folder containing their images.</p>
            <ul>
              <li>Excel file must have a 'name' column (required)</li>
              <li>Optional columns: 'age', 'gender', 'category'</li>
              <li>Data folder should contain subfolders named after each person</li>
              <li>Each person's subfolder should contain their images (JPG, PNG, JPEG)</li>
              <li>Valid categories: criminal, offender, chain snatching, eve teasing, unknown, eagle employee</li>
            </ul>
          </div>

          <div className="excel-bulk-form">
            <div className="form-row">
              <div className="form-section">
                <h4>1. Select Excel File</h4>
                <div
                  className="file-upload-area"
                  onClick={() => {
                    if (!isLoading) excelFileInputRef.current?.click();
                  }}
                  style={{ cursor: isLoading ? 'not-allowed' : 'pointer' }}
                >
                  <input
                    ref={excelFileInputRef}
                    type="file"
                    accept=".xlsx,.xls"
                    onChange={handleExcelFileSelect}
                    style={{ display: 'none' }}
                    disabled={isLoading}
                  />
                  <div className="upload-placeholder">
                    <div className="upload-icon">📊</div>
                    <p>{excelFile ? excelFile.name : 'Click to select Excel file'}</p>
                    <small>Supported: .xlsx, .xls</small>
                  </div>
                </div>
              </div>

              <div className="form-section">
                <h4>2. Select Data Folder</h4>
                <div
                  className="folder-select-area"
                  onClick={handleFolderSelect}
                  style={{ cursor: isLoading ? 'not-allowed' : 'pointer' }}
                >
                  <div className="upload-placeholder">
                    <div className="upload-icon">📂</div>
                    <p>{selectedFolder || 'Click to select data folder'}</p>
                    <small>Folder containing person subfolders</small>
                  </div>
                </div>
              </div>
            </div>

            <div className="form-actions">
              <button
                className="btn-primary"
                onClick={handleBulkRegistration}
                disabled={isLoading || !excelFile || !selectedFolder}
              >
                {isLoading ? 'Processing...' : 'Start Bulk Registration'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RegistrationWidget;
