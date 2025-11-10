#!/bin/bash
# Quick fix script to set up CUDA 12.3 library path

echo "Setting up CUDA 12.3 library path..."

# Add to current session
export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:$LD_LIBRARY_PATH
export PATH=/usr/local/cuda-12.3/bin:$PATH
export CUDA_HOME=/usr/local/cuda-12.3

# Make permanent by adding to ~/.bashrc
if ! grep -q "cuda-12.3" ~/.bashrc; then
    echo "" >> ~/.bashrc
    echo "# CUDA 12.3 paths" >> ~/.bashrc
    echo 'export PATH=/usr/local/cuda-12.3/bin:$PATH' >> ~/.bashrc
    echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.3/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
    echo 'export CUDA_HOME=/usr/local/cuda-12.3' >> ~/.bashrc
    echo "Added CUDA paths to ~/.bashrc"
else
    echo "CUDA paths already in ~/.bashrc"
fi

# Update library cache
sudo ldconfig

echo ""
echo "✓ CUDA paths configured!"
echo ""
echo "Current LD_LIBRARY_PATH:"
echo $LD_LIBRARY_PATH
echo ""
echo "Verifying libraries..."
ls -la /usr/local/cuda-12.3/lib64/libcublasLt.so* 2>/dev/null && echo "✓ CUDA libraries found" || echo "✗ Libraries not found"

echo ""
echo "Next steps:"
echo "1. Activate your Python environment: source /home/eagle/face_match/pyqt_env/bin/activate"
echo "2. Install onnxruntime-gpu: pip install onnxruntime-gpu"
echo "3. Test: python -c \"import onnxruntime as ort; print(ort.get_available_providers())\""

