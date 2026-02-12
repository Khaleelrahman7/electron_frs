import React, { useState, useRef, useEffect } from 'react';
import './RegistrationWidget.css';

import { API_BASE_URL as BASE_URL } from '../utils/apiConfig';

const RegistrationWidget = () => {
  const [activeMode, setActiveMode] = useState('single');
  const [formData, setFormData] = useState({
    name: '',
    age: '18',
    gender: 'Male',
    category: ''
  });
  const [autoDetectAge, setAutoDetectAge] = useState(true);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState(''); // 'success' or 'error'
  const [ageError, setAgeError] = useState('');
  const [categoryError, setCategoryError] = useState('');
  const fileInputRef = useRef(null);

  // Bulk registration with Excel + Folder
  const [excelFile, setExcelFile] = useState(null);
  const [selectedFolder, setSelectedFolder] = useState('');
  const [imageFilesForBulk, setImageFilesForBulk] = useState([]);
  const excelFileInputRef = useRef(null);

  // Ensure age is always 18 or above on component mount
  useEffect(() => {
    const ageNum = parseInt(formData.age, 10);
    if (!formData.age || isNaN(ageNum) || ageNum < 18) {
      setFormData(prev => ({ ...prev, age: '18' }));
      setAgeError('');
    }
  }, []);

  const handleInputChange = (field, value) => {
    // Validate age - must be 18 or above
    if (field === 'age') {
      const ageValue = value.trim();
      if (ageValue === '') {
        // If empty, set to 18 as default
        setAgeError('');
        setFormData(prev => ({ ...prev, [field]: '18' }));
        return;
      }
      const ageNum = parseInt(ageValue, 10);
      if (isNaN(ageNum) || ageNum < 18) {
        setAgeError('Age must be 18 or above');
      } else {
        setAgeError('');
      }
    }
    
    // Validate category - only letters and spaces, no numbers
    if (field === 'category') {
      const categoryValue = value.trim();
      if (categoryValue === '') {
        setCategoryError('');
        setFormData(prev => ({ ...prev, [field]: '' }));
        return;
      }
      // Allow only letters, spaces, and common punctuation for category names (no numbers)
      const categoryPattern = /^[a-zA-Z\s\-']+$/;
      if (!categoryPattern.test(categoryValue)) {
        setCategoryError('Category should only contain letters and spaces (no numbers allowed)');
        // Don't update the field if it contains numbers
        return;
      } else {
        setCategoryError('');
      }
    }
    
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
      age: '18',
      gender: 'Male',
      category: ''
    });
    setImageFile(null);
    setImagePreview(null);
    setAgeError('');
    setCategoryError('');
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

    // Validate age if provided
    if (formData.age.trim()) {
      const ageNum = parseInt(formData.age.trim(), 10);
      if (isNaN(ageNum) || ageNum < 18) {
        showMessage('Age must be 18 or above', 'error');
        setAgeError('Age must be 18 or above');
        return;
      }
    }

    // Validate category if provided
    if (formData.category.trim()) {
      const categoryPattern = /^[a-zA-Z\s\-']+$/;
      if (!categoryPattern.test(formData.category.trim())) {
        showMessage('Category should only contain letters and spaces (no numbers)', 'error');
        setCategoryError('Category should only contain letters and spaces (no numbers)');
        return;
      }
    }

    setIsLoading(true);
    setMessage('Registering person...');

    try {
      const formDataToSend = new FormData();
      formDataToSend.append('image', imageFile);
      formDataToSend.append('name', formData.name.trim());
      formDataToSend.append('age', autoDetectAge ? '' : (formData.age || ''));
      formDataToSend.append('gender', formData.gender);
      formDataToSend.append('category', formData.category.trim());

      const response = await fetch(`${BASE_URL}/api/registration/register/single`, {
        method: 'POST',
        body: formDataToSend,
      });

      const result = await response.json();

      if (response.ok && result.status === 'success') {
        const extra = result.age_range
          ? ` Age range: ${result.age_range}${result.age_source ? ` (${result.age_source})` : ''}.`
          : '';
        showMessage(`Successfully registered ${formData.name}!${extra}`, 'success');
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
        showMessage('Scanning folder for images...', 'success');
        
        const scanResult = await window.electronAPI.scanFolderForImages(result.folderPath);
        if (scanResult.success && scanResult.count > 0) {
          setImageFilesForBulk(scanResult.files);
          showMessage(`Folder selected: ${scanResult.count} image(s) found`, 'success');
        } else if (scanResult.success && scanResult.count === 0) {
          showMessage('Folder selected but no image files found', 'error');
          setImageFilesForBulk([]);
        } else {
          showMessage('Failed to scan folder', 'error');
          setImageFilesForBulk([]);
        }
      }
    } catch (error) {
      console.error('Error selecting folder:', error);
      showMessage('Failed to select folder', 'error');
      setImageFilesForBulk([]);
    }
  };

  const handleBulkRegistration = async () => {
    if (!excelFile) {
      showMessage('Please select an Excel file first', 'error');
      return;
    }

    if (imageFilesForBulk.length === 0) {
      showMessage('Please select a data folder with image files first', 'error');
      return;
    }

    setIsLoading(true);
    setMessage('Processing bulk registration...');

    try {
      const excelBuffer = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(new Uint8Array(e.target.result));
        reader.onerror = reject;
        reader.readAsArrayBuffer(excelFile);
      });

      const result = await window.electronAPI.registerBulk(
        Array.from(excelBuffer),
        imageFilesForBulk
      );

      if (result.success) {
        const successCount = result.data.filter(r => r.status === 'success').length;
        const totalCount = result.data.length;
        showMessage(`Bulk registration completed: ${successCount}/${totalCount} successful`, 'success');

        setExcelFile(null);
        setSelectedFolder('');
        setImageFilesForBulk([]);
        if (excelFileInputRef.current) {
          excelFileInputRef.current.value = '';
        }
      } else {
        showMessage(result.error || 'Bulk registration failed', 'error');
      }
    } catch (error) {
      console.error('Bulk registration error:', error);
      showMessage('Failed to process bulk registration. Please ensure the backend is running.', 'error');
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
                  <div className="toggle-row">
                    <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input
                        type="checkbox"
                        checked={autoDetectAge}
                        onChange={(e) => setAutoDetectAge(e.target.checked)}
                        disabled={isLoading}
                      />
                      Auto-detect from photo
                    </label>
                    {autoDetectAge && (
                      <span className="ai-badge">
                        High Accuracy AI
                      </span>
                    )}
                  </div>
                  <div className="age-stepper">
                    <button
                      type="button"
                      className="step-btn"
                      onClick={() => {
                        const current = parseInt(formData.age || '18', 10);
                        const next = isNaN(current) ? 18 : Math.max(18, current - 1);
                        setAgeError('');
                        setFormData(prev => ({ ...prev, age: String(next) }));
                      }}
                      disabled={isLoading || autoDetectAge || (() => {
                        const v = parseInt(formData.age || '18', 10);
                        return !isFinite(v) || v <= 18;
                      })()}
                    >
                      −
                    </button>
                    <input
                      type="number"
                      value={(() => {
                        const ageValue = formData.age || '18';
                        const ageNum = parseInt(ageValue, 10);
                        const finalValue = (isNaN(ageNum) || ageNum < 18) ? '18' : String(Math.min(120, ageNum));
                        return finalValue;
                      })()}
                      readOnly
                      min={18}
                      max={120}
                      step={1}
                      disabled={isLoading || autoDetectAge}
                    />
                    <button
                      type="button"
                      className="step-btn"
                      onClick={() => {
                        const current = parseInt(formData.age || '18', 10);
                        const next = isNaN(current) ? 18 : Math.min(120, current + 1);
                        setAgeError('');
                        setFormData(prev => ({ ...prev, age: String(next) }));
                      }}
                      disabled={isLoading || autoDetectAge || (() => {
                        const v = parseInt(formData.age || '18', 10);
                        return !isFinite(v) || v >= 120;
                      })()}
                    >
                      +
                    </button>
                  </div>
                  {ageError && <span className="field-error">{ageError}</span>}
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
                  placeholder="e.g., Employee, Visitor, Student (letters only)"
                  disabled={isLoading}
                  pattern="[a-zA-Z\s\-']+"
                  title="Category should only contain letters and spaces (no numbers)"
                />
                {categoryError && <span className="field-error">{categoryError}</span>}
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
            </div>
          </div>
          <div className="right-panel">
            <div className="form-section upload-section">
              <h3>Upload Photo</h3>
              <div
                className="image-upload-area"
                onClick={() => {
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
              <li>Data folder should contain images named of each person</li>
              {/* <li>Each person's subfolder should contain their image (JPG, PNG, JPEG)</li> */}
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
                    <small>Folder containing person images</small>
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
