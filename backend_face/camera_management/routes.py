from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import os
import logging
import numpy as np

from .models import (
    CameraCreateRequest, CameraUpdateRequest, CameraValidationRequest,
    CameraValidationResponse, CameraListResponse, CameraOperationResponse
)
from .service import EnhancedCameraService
from .streaming import get_stream_manager, CameraStreamManager
from .recording import get_recording_manager, CameraRecordingManager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/collections", tags=["Camera Collections"])

# Get data directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "camera_management")

# Create service instance
camera_service = EnhancedCameraService(DATA_DIR)

def get_camera_service() -> EnhancedCameraService:
    return camera_service

def get_stream_service() -> CameraStreamManager:
    return get_stream_manager()

def get_recording_service() -> CameraRecordingManager:
    return get_recording_manager()

@router.post("/validate-camera", response_model=CameraValidationResponse)
async def validate_camera(
    request: CameraValidationRequest,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Validate camera data including duplicate checking"""
    try:
        return service.validate_camera(request)
    except Exception as e:
        logger.error(f"Error validating camera: {e}")
        return CameraValidationResponse(
            valid=False,
            error="Validation failed. Please try again.",
            type="server_error"
        )

@router.get("/cameras", response_model=CameraListResponse)
async def get_cameras(
    page: int = 1,
    per_page: int = 6,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Get paginated list of cameras with collections"""
    try:
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 50:
            per_page = 6
            
        return service.get_cameras(page, per_page)
    except Exception as e:
        logger.error(f"Error getting cameras: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cameras")

@router.post("/cameras", response_model=CameraOperationResponse)
async def create_camera(
    request: CameraCreateRequest,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Create a new camera"""
    try:
        return service.create_camera(request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to create camera")

@router.put("/cameras/{camera_id}", response_model=CameraOperationResponse)
async def update_camera(
    camera_id: int,
    request: CameraUpdateRequest,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Update an existing camera"""
    try:
        return service.update_camera(camera_id, request)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to update camera")

@router.delete("/cameras/{camera_id}", response_model=CameraOperationResponse)
async def delete_camera(
    camera_id: int,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Delete a camera"""
    try:
        return service.delete_camera(camera_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete camera")

@router.get("/cameras/{camera_id}")
async def get_camera(
    camera_id: int,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Get a specific camera by ID"""
    try:
        cameras = service._load_cameras()
        camera = next((c for c in cameras if c.id == camera_id), None)

        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        return camera
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve camera")

@router.post("/cameras/{camera_id}/activate")
async def activate_camera(
    camera_id: int,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Activate a camera"""
    try:
        return service.activate_camera(camera_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error activating camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate camera")

@router.post("/cameras/{camera_id}/deactivate")
async def deactivate_camera(
    camera_id: int,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Deactivate a camera"""
    try:
        return service.deactivate_camera(camera_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deactivating camera: {e}")
        raise HTTPException(status_code=500, detail="Failed to deactivate camera")

# Streaming endpoints
@router.post("/cameras/{camera_id}/start-stream")
async def start_camera_stream(
    camera_id: int,
    service: EnhancedCameraService = Depends(get_camera_service),
    stream_service: CameraStreamManager = Depends(get_stream_service)
):
    """Start streaming for a camera"""
    try:
        # Get camera info
        cameras = service._load_cameras()
        camera = next((c for c in cameras if c.id == camera_id), None)

        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Check if stream already exists
        existing_stream = stream_service.get_camera_stream(camera_id)
        if existing_stream:
            return {
                "success": True,
                "stream_id": existing_stream,
                "message": "Stream already active"
            }

        # Start new stream
        stream_id = stream_service.start_stream(camera_id, camera.rtsp_url)

        return {
            "success": True,
            "stream_id": stream_id,
            "message": "Stream started successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting stream for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start stream")

@router.delete("/cameras/{camera_id}/stop-stream")
async def stop_camera_stream(
    camera_id: int,
    stream_service: CameraStreamManager = Depends(get_stream_service)
):
    """Stop streaming for a camera"""
    try:
        stream_id = stream_service.get_camera_stream(camera_id)
        if not stream_id:
            raise HTTPException(status_code=404, detail="No active stream found for camera")

        success = stream_service.stop_stream(stream_id)
        if success:
            return {"success": True, "message": "Stream stopped successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to stop stream")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping stream for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop stream")

@router.get("/cameras/{camera_id}/stream")
async def get_camera_stream(
    camera_id: int,
    service: EnhancedCameraService = Depends(get_camera_service),
    stream_service: CameraStreamManager = Depends(get_stream_service)
):
    """Get MJPEG stream for a camera"""
    try:
        # Get camera info
        cameras = service._load_cameras()
        camera = next((c for c in cameras if c.id == camera_id), None)

        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Get or create stream
        stream_id = stream_service.get_camera_stream(camera_id)
        if not stream_id:
            stream_id = stream_service.start_stream(camera_id, camera.rtsp_url)

        # Return MJPEG stream
        return StreamingResponse(
            stream_service.generate_mjpeg_stream(stream_id),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stream for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stream")

@router.get("/cameras/{camera_id}/frame")
async def get_camera_frame(
    camera_id: int,
    service: EnhancedCameraService = Depends(get_camera_service),
    stream_service: CameraStreamManager = Depends(get_stream_service)
):
    """Get a single JPEG frame from camera (optimized for live streaming)"""
    try:
        from fastapi.responses import Response
        import cv2
        import numpy as np
        import datetime
        import time

        # Get camera info
        cameras = service._load_cameras()
        camera = next((c for c in cameras if c.id == camera_id), None)

        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        frame = None
        is_demo = False

        # Try to get frame from real camera with optimized settings
        try:
            cap = cv2.VideoCapture(camera.rtsp_url)
            if cap.isOpened():
                # Set properties for faster frame capture
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer to get latest frame
                cap.set(cv2.CAP_PROP_FPS, 30)  # Set target FPS
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)  # Set reasonable resolution
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
                
                # Try to get a fresh frame quickly
                for _ in range(2):  # Flush old frames
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        # Quick quality check
                        if np.mean(frame) > 5:  # Frame has meaningful content
                            break
                
            cap.release()
            
            # Validate frame
            if frame is not None and frame.size > 0 and np.mean(frame) > 5:
                logger.debug(f"✅ Real frame captured from camera {camera_id}")
            else:
                frame = None  # Force demo mode
                logger.debug(f"⚠️ Poor quality frame from camera {camera_id}, using demo")
                
        except Exception as e:
            logger.debug(f"📷 Camera {camera_id} unavailable: {e}")
            frame = None

        # Enhanced demo frame with smoother animation
        if frame is None:
            is_demo = True
            
            # Create demo frame with better resolution
            frame = np.zeros((540, 960, 3), dtype=np.uint8)

            # Smoother animation based on time
            current_time = time.time()
            wave_phase = (current_time * 2) % (2 * np.pi)  # 2 second cycle
            
            # Animated gradient background
            for y in range(540):
                for x in range(960):
                    # Smooth wave animation
                    wave_x = (x + int(100 * np.sin(wave_phase))) % 960
                    frame[y, x] = [
                        int(40 + (wave_x / 960) * 120 + 20 * np.sin(y / 40 + wave_phase)),  # Blue
                        int(20 + (y / 540) * 100 + 15 * np.cos(wave_x / 50 + wave_phase)),   # Green
                        int(60 + ((wave_x + y) / 1500) * 140)  # Red
                    ]

            # Add dynamic elements
            timestamp_str = datetime.datetime.now().strftime("%H:%M:%S")
            
            # Smooth moving elements
            circle_x = int(480 + 300 * np.sin(current_time * 0.8))
            circle_y = int(270 + 150 * np.cos(current_time * 0.6))
            cv2.circle(frame, (circle_x, circle_y), 25, (0, 255, 255), -1)
            cv2.circle(frame, (circle_x, circle_y), 30, (255, 255, 255), 2)
            
            # Secondary moving element
            pulse_radius = int(15 + 8 * np.sin(current_time * 3))
            pulse_x = int(480 + 180 * np.cos(current_time * 0.4))
            pulse_y = int(270 + 90 * np.sin(current_time * 0.5))
            cv2.circle(frame, (pulse_x, pulse_y), pulse_radius, (255, 128, 0), -1)

            # Text overlays
            cv2.putText(frame, f"DEMO CAMERA {camera_id}", (50, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
            cv2.putText(frame, f"DEMO CAMERA {camera_id}", (50, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
            
            cv2.putText(frame, f"Time: {timestamp_str}", (50, 110),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
            
            cv2.putText(frame, "STATUS: DEMO MODE - LIVE", (50, 470),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
            cv2.putText(frame, "STATUS: DEMO MODE - LIVE", (50, 470),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
            
            # Frame counter for continuous feedback
            frame_number = int(current_time * 10) % 99999  # 10 FPS simulation
            cv2.putText(frame, f"Frame: #{frame_number:05d}", (650, 500),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # Optimized JPEG encoding for fast delivery
        encode_params = [
            cv2.IMWRITE_JPEG_QUALITY, 75,  # Balanced quality for speed
            cv2.IMWRITE_JPEG_PROGRESSIVE, 0,  # Disable progressive for faster decode
            cv2.IMWRITE_JPEG_OPTIMIZE, 1   # Optimize file size
        ]
        
        ret, buffer = cv2.imencode('.jpg', frame, encode_params)
        if not ret:
            raise HTTPException(status_code=500, detail="Failed to encode frame")

        # Headers optimized for streaming
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Content-Type": "image/jpeg",
            "X-Frame-Source": "demo" if is_demo else "camera",
            "X-Camera-ID": str(camera_id),
            "X-Timestamp": str(int(time.time() * 1000)),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "*"
        }

        return Response(
            content=buffer.tobytes(),
            media_type="image/jpeg",
            headers=headers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting frame for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get frame")

# Recording endpoints
@router.post("/cameras/{camera_id}/start-recording")
async def start_camera_recording(
    camera_id: int,
    duration_minutes: Optional[int] = None,
    service: EnhancedCameraService = Depends(get_camera_service),
    recording_service: CameraRecordingManager = Depends(get_recording_service)
):
    """Start recording from a camera"""
    try:
        # Get camera info
        cameras = service._load_cameras()
        camera = next((c for c in cameras if c.id == camera_id), None)

        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Start recording
        recording_id = recording_service.start_recording(
            camera_id,
            camera.rtsp_url,
            duration_minutes
        )

        return {
            "success": True,
            "recording_id": recording_id,
            "message": "Recording started successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting recording for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start recording")

@router.post("/cameras/{camera_id}/stop-recording/{recording_id}")
async def stop_camera_recording(
    camera_id: int,
    recording_id: str,
    recording_service: CameraRecordingManager = Depends(get_recording_service)
):
    """Stop a camera recording"""
    try:
        success = recording_service.stop_recording(recording_id)
        if success:
            return {"success": True, "message": "Recording stopped successfully"}
        else:
            raise HTTPException(status_code=404, detail="Recording not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping recording {recording_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop recording")

@router.get("/cameras/{camera_id}/recordings")
async def get_camera_recordings(
    camera_id: int,
    recording_service: CameraRecordingManager = Depends(get_recording_service)
):
    """Get all recordings for a camera"""
    try:
        return recording_service.get_camera_recordings(camera_id)
    except Exception as e:
        logger.error(f"Error getting recordings for camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recordings")

@router.get("/recordings/active")
async def get_active_recordings(
    recording_service: CameraRecordingManager = Depends(get_recording_service)
):
    """Get all active recordings"""
    try:
        return recording_service.get_active_recordings()
    except Exception as e:
        logger.error(f"Error getting active recordings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active recordings")

# Collection management endpoints
@router.get("/")
async def get_collections(
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Get all collections"""
    try:
        collections = service._load_collections()
        return {"collections": collections}
    except Exception as e:
        logger.error(f"Error getting collections: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve collections")

@router.post("/")
async def create_collection(
    name: str,
    description: str = None,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Create a new collection"""
    try:
        import uuid
        from datetime import datetime
        from .models import CameraCollection
        
        collections = service._load_collections()
        
        # Check for duplicate names
        if any(c.name.lower() == name.lower() for c in collections):
            raise HTTPException(status_code=409, detail="Collection name already exists")
        
        new_collection = CameraCollection(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            created_at=datetime.now(),
            camera_count=0
        )
        
        collections.append(new_collection)
        service._save_collections(collections)
        
        return {"success": True, "collection": new_collection}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to create collection")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "camera_management"}
