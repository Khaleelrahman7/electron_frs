# CUDA Installation Guide for Linux Server

## Step 1: Check System Requirements

```bash
# Check Linux version
lsb_release -a
# or
cat /etc/os-release

# Check if you have NVIDIA GPU
lspci | grep -i nvidia

# Check current NVIDIA driver (if any)
nvidia-smi
```

## Step 2: Install NVIDIA Drivers (if not installed)

```bash
# Update package list
sudo apt update

# Install NVIDIA driver (for Ubuntu/Debian)
# For Tesla T4, use driver version 470 or newer
sudo apt install nvidia-driver-535  # or latest available version

# Alternative: Use NVIDIA's official repository
# Add NVIDIA repository
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt update
sudo apt install -y nvidia-driver-535

# Reboot after driver installation
sudo reboot
```

## Step 3: Verify NVIDIA Driver

After reboot:
```bash
nvidia-smi
# Should show your Tesla T4 GPU
```

## Step 4: Install CUDA Toolkit

### Option A: Install CUDA via Package Manager (Recommended)

```bash
# For Ubuntu 20.04/22.04
# Add NVIDIA CUDA repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update

# Install CUDA 12.x (latest stable)
sudo apt-get install -y cuda-toolkit-12-3

# OR install specific version
sudo apt-get install -y cuda-toolkit-12-2

# Set up environment variables
echo 'export PATH=/usr/local/cuda-12.3/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

### Option B: Install CUDA via Runfile (Alternative)

```bash
# Download CUDA installer (choose version)
# For CUDA 12.3:
wget https://developer.download.nvidia.com/compute/cuda/12.3.0/local_installers/cuda_12.3.0_545.23.06_linux.run

# Make executable
chmod +x cuda_12.3.0_545.23.06_linux.run

# Install (accept license, don't install driver if already installed)
sudo ./cuda_12.3.0_545.23.06_linux.run

# Set environment variables
echo 'export PATH=/usr/local/cuda-12.3/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc
```

## Step 5: Verify CUDA Installation

```bash
# Check CUDA version
nvcc --version

# Verify CUDA libraries
ls -la /usr/local/cuda*/lib64/libcublasLt.so*

# Test CUDA
cd /usr/local/cuda-12.3/samples/1_Utilities/deviceQuery
sudo make
./deviceQuery
```

## Step 6: Install cuDNN (Required for Deep Learning)

```bash
# Option A: Via apt (easier)
# Add NVIDIA cuDNN repository
sudo apt-get install -y zlib1g
sudo apt-get install -y libcudnn8=8.9.*-1+cuda12.3
sudo apt-get install -y libcudnn8-dev=8.9.*-1+cuda12.3

# Option B: Manual installation
# 1. Download cuDNN from NVIDIA (requires free account)
#    https://developer.nvidia.com/cudnn
#    Download cuDNN v8.9.x for CUDA 12.x

# 2. Extract and copy files
tar -xvf cudnn-linux-x86_64-8.9.x.x_cuda12.x-archive.tar.xz
sudo cp cudnn-*-archive/include/cudnn*.h /usr/local/cuda-12.3/include
sudo cp -P cudnn-*-archive/lib/libcudnn* /usr/local/cuda-12.3/lib64
sudo chmod a+r /usr/local/cuda-12.3/include/cudnn*.h /usr/local/cuda-12.3/lib64/libcudnn*
```

## Step 7: Update Library Cache

```bash
# Update dynamic linker cache
sudo ldconfig

# Verify libraries are found
ldconfig -p | grep cublas
ldconfig -p | grep cudnn
```

## Step 8: Install ONNXRuntime GPU in Python Environment

```bash
# Activate your virtual environment
source /home/eagle/face_match/pyqt_env/bin/activate

# Uninstall CPU version if installed
pip uninstall onnxruntime -y

# Install GPU version
pip install onnxruntime-gpu

# Verify installation
python -c "import onnxruntime as ort; print('Providers:', ort.get_available_providers())"
# Should show: ['CUDAExecutionProvider', 'CPUExecutionProvider']
```

## Step 9: Test GPU Access

```bash
# Test with Python
python -c "
import onnxruntime as ort
providers = ort.get_available_providers()
print('Available providers:', providers)
if 'CUDAExecutionProvider' in providers:
    print('✓ CUDA provider is available!')
    # Try to create a simple session
    try:
        import numpy as np
        providers_list = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        print('✓ GPU is ready to use')
    except Exception as e:
        print('✗ GPU initialization error:', e)
else:
    print('✗ CUDA provider NOT available')
    print('Check LD_LIBRARY_PATH and CUDA installation')
"
```

## Step 10: Set Permanent Environment Variables

Add to `~/.bashrc` or create `/etc/profile.d/cuda.sh`:

```bash
# Add these lines to ~/.bashrc
export PATH=/usr/local/cuda-12.3/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:$LD_LIBRARY_PATH
export CUDA_HOME=/usr/local/cuda-12.3

# For system-wide (optional)
sudo tee /etc/profile.d/cuda.sh << EOF
export PATH=/usr/local/cuda-12.3/bin:\$PATH
export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:\$LD_LIBRARY_PATH
export CUDA_HOME=/usr/local/cuda-12.3
EOF

# Reload
source ~/.bashrc
```

## Troubleshooting

### If nvidia-smi works but CUDA doesn't:

```bash
# Check library paths
echo $LD_LIBRARY_PATH
ldconfig -p | grep cuda

# Manually add to current session
export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:$LD_LIBRARY_PATH
```

### If ONNXRuntime still can't find CUDA:

```bash
# Check if libraries exist
find /usr/local -name "libcublasLt.so*" 2>/dev/null
find /usr/lib -name "libcublasLt.so*" 2>/dev/null

# Add all possible paths
export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
```

### Check CUDA compatibility:

```bash
# Verify CUDA and driver compatibility
nvidia-smi  # Shows driver version
nvcc --version  # Shows CUDA toolkit version

# Driver version should be >= CUDA version requirements
# CUDA 12.3 requires driver >= 535.54.03
```

## Quick Installation Script

For Ubuntu 22.04, you can run:

```bash
#!/bin/bash
# Quick CUDA installation script

# Install NVIDIA driver
sudo apt update
sudo apt install -y nvidia-driver-535

# Add CUDA repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update

# Install CUDA
sudo apt-get install -y cuda-toolkit-12-3

# Install cuDNN
sudo apt-get install -y libcudnn8=8.9.*-1+cuda12.3
sudo apt-get install -y libcudnn8-dev=8.9.*-1+cuda12.3

# Set environment
echo 'export PATH=/usr/local/cuda-12.3/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
echo 'export CUDA_HOME=/usr/local/cuda-12.3' >> ~/.bashrc

# Update library cache
sudo ldconfig

echo "CUDA installation complete. Please reboot and then run: nvidia-smi"
```

## After Installation

1. **Reboot the server** (if driver was installed)
2. **Verify**: `nvidia-smi` should show your Tesla T4
3. **Verify**: `nvcc --version` should show CUDA version
4. **Test**: Run the Python test script above
5. **Restart backend**: The face pipeline will automatically use GPU

## Notes

- **CUDA Version**: Use CUDA 12.x for best compatibility with modern libraries
- **Driver Version**: Must be compatible with CUDA version (check NVIDIA compatibility matrix)
- **cuDNN**: Required for InsightFace and other deep learning frameworks
- **Virtual Environment**: Make sure to install `onnxruntime-gpu` in your Python environment

