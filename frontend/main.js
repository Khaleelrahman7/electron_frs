const { app, BrowserWindow, Menu, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');
const axios = require('axios');
const FormData = require('form-data');
const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged;

function loadFallbackPage(mainWindow) {
  const fallbackHtml = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Face Recognition System</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 40px; text-align: center; }
        .error { color: #e74c3c; }
        .info { color: #3498db; }
      </style>
    </head>
    <body>
      <h1>Face Recognition System</h1>
      <div class="error">
        <h2>Build files not found</h2>
        <p>Please run the following commands to build the application:</p>
        <pre>npm run build</pre>
        <p>Then restart the application.</p>
      </div>
      <div class="info">
        <p>Backend Status: <span id="backend-status">Checking...</span></p>
      </div>
      <script>
        // Check backend status
        fetch('http://localhost:8000/health')
          .then(() => {
            document.getElementById('backend-status').textContent = 'Running ✅';
            document.getElementById('backend-status').style.color = '#27ae60';
          })
          .catch(() => {
            document.getElementById('backend-status').textContent = 'Not Running ❌';
            document.getElementById('backend-status').style.color = '#e74c3c';
          });
      </script>
    </body>
    </html>
  `;

  mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(fallbackHtml)}`);
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, 'assets/icon.png'), // Add your app icon
    titleBarStyle: 'default',
    show: false
  });

  // Load the app
  if (isDev) {
    // In development, try to load from development server first
    mainWindow.loadURL('http://localhost:3000').catch(() => {
      // If dev server is not running, fall back to build
      const buildPath = path.join(__dirname, 'build/index.html');
      if (fs.existsSync(buildPath)) {
        mainWindow.loadFile(buildPath);
      } else {
        // Show fallback page
        loadFallbackPage(mainWindow);
      }
    });
    // Open dev tools in development mode
    mainWindow.webContents.openDevTools();
  } else {
    // In production, load from build directory
    const buildPath = path.join(__dirname, 'build/index.html');
    if (fs.existsSync(buildPath)) {
      mainWindow.loadFile(buildPath);
    } else {
      // Show fallback page
      loadFallbackPage(mainWindow);
    }
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Create application menu
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Refresh',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            mainWindow.reload();
          }
        },
        {
          label: 'Exit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Toggle Developer Tools',
          accelerator: process.platform === 'darwin' ? 'Alt+Cmd+I' : 'Ctrl+Shift+I',
          click: () => {
            mainWindow.webContents.toggleDevTools();
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// IPC Handlers for Video Processing
ipcMain.handle('check-backend-status', async () => {
  try {
    const response = await axios.get('http://localhost:8000/api/status', { timeout: 5000 });
    return {
      success: true,
      available: true,
      status: response.data
    };
  } catch (error) {
    return {
      success: false,
      available: false,
      error: error.message
    };
  }
});

ipcMain.handle('select-video-file', async () => {
  try {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [
        { name: 'Video Files', extensions: ['mp4', 'avi', 'mov', 'mkv', 'wmv'] }
      ]
    });

    if (result.canceled) {
      return { success: false };
    }

    return {
      success: true,
      filePath: result.filePaths[0]
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('upload-video', async (event, filePath) => {
  try {
    const formData = new FormData();
    formData.append('video', fs.createReadStream(filePath));

    const response = await axios.post('http://localhost:8000/api/video/upload', formData, {
      headers: formData.getHeaders(),
      timeout: 30000
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('start-processing', async (event, videoId, options) => {
  try {
    const response = await axios.post(`http://localhost:8000/api/video/process/${videoId}`, options, {
      timeout: 10000
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-process-status', async (event, taskId) => {
  try {
    const response = await axios.get(`http://localhost:8000/api/video/status/${taskId}`, {
      timeout: 5000
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-process-result', async (event, taskId) => {
  try {
    const response = await axios.get(`http://localhost:8000/api/video/result/${taskId}`, {
      timeout: 10000
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('cancel-processing', async (event, taskId) => {
  try {
    const response = await axios.post(`http://localhost:8000/api/video/cancel/${taskId}`, {}, {
      timeout: 5000
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('delete-video', async (event, videoId) => {
  try {
    const response = await axios.delete(`http://localhost:8000/api/video/${videoId}`, {
      timeout: 5000
    });

    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC Handlers for Enhanced Camera Management
ipcMain.handle('get-camera-list', async () => {
  try {
    const response = await axios.get('http://localhost:8000/api/collections/cameras', { timeout: 5000 });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('add-camera', async (event, config) => {
  try {
    const response = await axios.post('http://localhost:8000/api/collections/cameras', {
      name: config.name || 'Camera',
      rtsp_url: config.rtsp_url,
      collection_id: config.collection_id || 'default'
    }, {
      timeout: 10000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('remove-camera', async (event, cameraId) => {
  try {
    const response = await axios.delete(`http://localhost:8000/api/collections/cameras/${cameraId}`, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('validate-camera', async (event, validationData) => {
  try {
    const response = await axios.post('http://localhost:8000/api/collections/validate-camera', validationData, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

// Enhanced camera activation/deactivation
ipcMain.handle('activate-camera', async (event, cameraId) => {
  try {
    const response = await axios.post(`http://localhost:8000/api/collections/cameras/${cameraId}/activate`, {}, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('deactivate-camera', async (event, cameraId) => {
  try {
    const response = await axios.post(`http://localhost:8000/api/collections/cameras/${cameraId}/deactivate`, {}, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-camera-frame', async (event, cameraId) => {
  try {
    // Get camera stream URL for frame retrieval
    const response = await axios.get(`http://localhost:8000/api/collections/cameras/${cameraId}/stream`, {
      timeout: 5000,
      responseType: 'stream'
    });
    return {
      success: true,
      streamUrl: `http://localhost:8000/api/collections/cameras/${cameraId}/stream`
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

// New streaming handlers
ipcMain.handle('start-camera-stream', async (event, cameraId) => {
  try {
    const response = await axios.post(`http://localhost:8000/api/collections/cameras/${cameraId}/start-stream`, {}, {
      timeout: 10000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('stop-camera-stream', async (event, cameraId) => {
  try {
    const response = await axios.delete(`http://localhost:8000/api/collections/cameras/${cameraId}/stop-stream`, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

// Recording handlers
ipcMain.handle('start-camera-recording', async (event, cameraId, durationMinutes) => {
  try {
    const response = await axios.post(`http://localhost:8000/api/collections/cameras/${cameraId}/start-recording`, {
      duration_minutes: durationMinutes
    }, {
      timeout: 10000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('stop-camera-recording', async (event, cameraId, recordingId) => {
  try {
    const response = await axios.post(`http://localhost:8000/api/collections/cameras/${cameraId}/stop-recording/${recordingId}`, {}, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-camera-recordings', async (event, cameraId) => {
  try {
    const response = await axios.get(`http://localhost:8000/api/collections/cameras/${cameraId}/recordings`, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-active-recordings', async (event) => {
  try {
    const response = await axios.get(`http://localhost:8000/api/collections/recordings/active`, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-camera-status', async (event, cameraId) => {
  try {
    // Get camera status from the enhanced system
    const response = await axios.get(`http://localhost:8000/api/collections/cameras/${cameraId}`, {
      timeout: 5000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC Handlers for Registration
ipcMain.handle('register-single', async (event, formData) => {
  try {
    const response = await axios.post('http://localhost:8000/api/registration/single', formData, {
      headers: formData.getHeaders ? formData.getHeaders() : { 'Content-Type': 'multipart/form-data' },
      timeout: 30000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('register-bulk', async (event, formData) => {
  try {
    const response = await axios.post('http://localhost:8000/api/registration/bulk', formData, {
      headers: formData.getHeaders ? formData.getHeaders() : { 'Content-Type': 'multipart/form-data' },
      timeout: 60000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('get-registered-faces', async () => {
  try {
    const response = await axios.get('http://localhost:8000/api/registration/gallery', {
      timeout: 10000
    });
    return {
      success: true,
      data: response.data
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC Handlers for File Operations
ipcMain.handle('select-file', async (event, options = {}) => {
  try {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: options.filters || [
        { name: 'All Files', extensions: ['*'] }
      ]
    });

    if (result.canceled) {
      return { success: false };
    }

    return {
      success: true,
      filePath: result.filePaths[0]
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('select-folder', async () => {
  try {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory']
    });

    if (result.canceled) {
      return { success: false };
    }

    return {
      success: true,
      folderPath: result.filePaths[0]
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

// IPC Handlers for Utility Functions
ipcMain.handle('show-message-box', async (event, options) => {
  try {
    const result = await dialog.showMessageBox(options);
    return {
      success: true,
      response: result.response,
      checkboxChecked: result.checkboxChecked
    };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

ipcMain.handle('show-error-dialog', async (event, title, content) => {
  try {
    await dialog.showErrorBox(title, content);
    return { success: true };
  } catch (error) {
    return {
      success: false,
      error: error.message
    };
  }
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
