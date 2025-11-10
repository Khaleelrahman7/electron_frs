# GPU Setup Guide for Tesla T4

## Issue: CUDA Library Not Found

The error `libcublasLt.so.12: cannot open shared object file` indicates that CUDA libraries are not in the library path.

**If CUDA is not installed at all**, see `CUDA_INSTALLATION.md` for complete installation instructions.

## Solution Steps

### 1. Check CUDA Installation

```bash
# Check CUDA version
nvcc --version

# Check if CUDA libraries exist
find /usr/local/cuda* -name "libcublasLt.so*" 2>/dev/null
find /usr/lib/x86_64-linux-gnu -name "libcublasLt.so*" 2>/dev/null
```

### 2. Set LD_LIBRARY_PATH

Add CUDA library path to environment:

```bash
# Find your CUDA installation (usually one of these)
export LD_LIBRARY_PATH=/usr/local/cuda-12.x/lib64:$LD_LIBRARY_PATH
# OR
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH

# Make it permanent by adding to ~/.bashrc or ~/.profile
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.x/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### 3. Verify ONNXRuntime GPU Support

```bash
# Activate your virtual environment
source /home/eagle/face_match/pyqt_env/bin/activate

# Check if onnxruntime-gpu is installed
pip list | grep onnxruntime

# If you see 'onnxruntime' (CPU only), install GPU version:
pip uninstall onnxruntime
pip install onnxruntime-gpu

# Verify CUDA provider is available
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
# Should show: ['CUDAExecutionProvider', 'CPUExecutionProvider']
```

### 4. Check cuDNN Installation

```bash
# Check if cuDNN is installed
find /usr/local/cuda* -name "*cudnn*" 2>/dev/null
find /usr/lib/x86_64-linux-gnu -name "*cudnn*" 2>/dev/null

# If not found, install cuDNN (version should match CUDA)
# For CUDA 12.x, install cuDNN 8.x
```

### 5. Alternative: Use System-Wide Library Path

If libraries are in system directories, ensure they're accessible:

```bash
# Update library cache
sudo ldconfig

# Check if libraries are found
ldconfig -p | grep cublas
```

### 6. Test GPU Access

```bash
# Test with Python
python -c "
import onnxruntime as ort
providers = ort.get_available_providers()
print('Available providers:', providers)
if 'CUDAExecutionProvider' in providers:
    print('✓ CUDA provider available')
else:
    print('✗ CUDA provider NOT available')
"
```

## Performance Optimizations Applied

The code now includes:

1. **Frame Skipping**: Processes every 2nd frame (configurable via `PROCESS_EVERY_N_FRAMES`)
2. **Frame Downscaling**: Processes at max 1280px width for speed
3. **Fast Encoding**: Uses `num_jitters=0` and `model='small'` for face_recognition
4. **Auto GPU Detection**: Automatically falls back to CPU if GPU unavailable
5. **Small Face Filtering**: Skips faces smaller than 30x30 pixels

## Configuration

To adjust performance, modify these values in `face_pipeline.py`:

- `PROCESS_EVERY_N_FRAMES = 2` - Increase for faster processing (less accuracy)
- `max_width = 1280` - Decrease for faster processing (lower quality)
- `det_size=(640, 640)` - Increase for better detection (slower)

## Running the Server

After fixing CUDA libraries, restart the server:

```bash
cd /home/eagle/FRS/backend_face
source /home/eagle/face_match/pyqt_env/bin/activate
python start_server.py
```

The server will automatically detect and use GPU if available.

