from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import os
import logging

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
    """Get a single JPEG frame from camera (better browser compatibility)"""
    try:
        from fastapi.responses import Response
        import cv2
        import numpy as np
        import datetime

        # Get camera info
        cameras = service._load_cameras()
        camera = next((c for c in cameras if c.id == camera_id), None)

        if not camera:
            raise HTTPException(status_code=404, detail="Camera not found")

        # Try to get frame from real camera first
        cap = cv2.VideoCapture(camera.rtsp_url)
        frame = None

        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()

        # If real camera failed, generate demo frame
        if frame is None:
            # Create demo frame (640x480)
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            # Add gradient background
            for y in range(480):
                for x in range(640):
                    frame[y, x] = [
                        int(50 + (x / 640) * 100),  # Blue gradient
                        int(30 + (y / 480) * 80),   # Green gradient
                        int(80 + ((x + y) / 1120) * 100)  # Red gradient
                    ]

            # Add camera info text
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Add text overlays
            cv2.putText(frame, f"DEMO CAMERA {camera_id}", (50, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(frame, f"Time: {current_time}", (50, 100),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(frame, "Camera Offline - Demo Mode", (50, 400),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

            # Add moving circle
            import time
            elapsed = time.time() % 10  # 10 second cycle
            circle_x = int(320 + 200 * np.sin(elapsed))
            circle_y = int(240 + 100 * np.cos(elapsed * 1.5))
            cv2.circle(frame, (circle_x, circle_y), 20, (0, 255, 255), -1)

        # Encode frame as JPEG
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ret:
            raise HTTPException(status_code=500, detail="Failed to encode frame")

        return Response(
            content=buffer.tobytes(),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
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
