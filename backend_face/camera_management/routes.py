from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Optional
import os
import logging
import numpy as np

from .models import (
    CameraCreateRequest, CameraUpdateRequest, CameraValidationRequest,
    CameraValidationResponse, CameraListResponse, CameraOperationResponse,
    CollectionCreateRequest, CollectionUpdateRequest
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

        # Try to get frame from real camera with ultra-fast settings
        try:
            cap = cv2.VideoCapture(camera.rtsp_url)
            if cap.isOpened():
                # Optimized settings for minimum latency
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
                cap.set(cv2.CAP_PROP_FPS, 15)  # Moderate FPS to reduce load
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Smaller resolution for speed
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                
                # Quick frame grab with timeout
                start_time = time.time()
                ret, frame = cap.read()
                grab_time = time.time() - start_time
                
                if ret and frame is not None and frame.size > 0:
                    # Quick quality validation
                    if np.mean(frame) > 10 and grab_time < 2.0:  # Frame quality and speed check
                        logger.debug(f"✅ Real frame captured from camera {camera_id} in {grab_time:.2f}s")
                    else:
                        frame = None  # Will retry instead of using demo
                        logger.debug(f"⚠️ Slow/poor frame from camera {camera_id}, will retry")
                else:
                    frame = None
                    
            cap.release()
                
        except Exception as e:
            logger.debug(f"📷 Camera {camera_id} unavailable: {e}")
            frame = None

        # If frame is None, keep retrying instead of showing demo
        # Retry up to 3 times with short delays
        if frame is None:
            for retry in range(3):
                try:
                    time.sleep(0.1)  # Short delay before retry
                    cap = cv2.VideoCapture(camera.rtsp_url)
                    if cap.isOpened():
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        ret, frame = cap.read()
                        if ret and frame is not None and frame.size > 0:
                            cap.release()
                            break
                    cap.release()
                except Exception as e:
                    logger.debug(f"Retry {retry + 1} failed for camera {camera_id}: {e}")
            
            # If still no frame after retries, return error instead of demo
            if frame is None:
                raise HTTPException(
                    status_code=503,
                    detail=f"Camera {camera_id} is currently unavailable. Please check the camera connection."
                )

        # Ultra-optimized JPEG encoding for speed
        encode_params = [
            cv2.IMWRITE_JPEG_QUALITY, 70,  # Slightly lower quality for speed
            cv2.IMWRITE_JPEG_PROGRESSIVE, 0,  # Baseline JPEG for fastest decode
            cv2.IMWRITE_JPEG_OPTIMIZE, 0   # Skip optimization for speed
        ]
        
        ret, buffer = cv2.imencode('.jpg', frame, encode_params)
        if not ret:
            raise HTTPException(status_code=500, detail="Failed to encode frame")

        # Headers optimized for streaming with cache busting
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "Content-Type": "image/jpeg",
            "X-Frame-Source": "camera",
            "X-Camera-ID": str(camera_id),
            "X-Timestamp": str(int(time.time() * 1000)),
            "X-Frame-Time": datetime.datetime.now().isoformat(),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "*"
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
    request: CollectionCreateRequest,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Create a new collection"""
    try:
        import uuid
        from datetime import datetime
        from .models import CameraCollection
        
        collections = service._load_collections()
        
        # Check for duplicate names
        if any(c.name.lower() == request.name.lower() for c in collections):
            raise HTTPException(status_code=409, detail="Collection name already exists")
        
        new_collection = CameraCollection(
            id=str(uuid.uuid4()),
            name=request.name,
            description=request.description,
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

@router.put("/{collection_id}")
async def update_collection(
    collection_id: str,
    request: CollectionUpdateRequest,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Update a collection"""
    try:
        collections = service._load_collections()
        
        # Find the collection to update
        collection = next((c for c in collections if c.id == collection_id), None)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # Check if it's the default collection
        if collection_id == "default" and request.name and request.name.lower() != "default collection":
            raise HTTPException(status_code=400, detail="Cannot rename the default collection")
        
        # Check for duplicate names (excluding current collection)
        if request.name:
            if any(c.name.lower() == request.name.lower() and c.id != collection_id for c in collections):
                raise HTTPException(status_code=409, detail="Collection name already exists")
            collection.name = request.name
        
        if request.description is not None:
            collection.description = request.description
        
        service._save_collections(collections)
        
        # Update collection name in all cameras
        if request.name:
            cameras = service._load_cameras()
            for camera in cameras:
                if camera.collection_id == collection_id:
                    camera.collection_name = collection.name
            service._save_cameras(cameras)
        
        return {"success": True, "collection": collection}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to update collection")

@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    service: EnhancedCameraService = Depends(get_camera_service)
):
    """Delete a collection"""
    try:
        # Prevent deletion of default collection
        if collection_id == "default":
            raise HTTPException(status_code=400, detail="Cannot delete the default collection")
        
        collections = service._load_collections()
        
        # Find the collection
        collection = next((c for c in collections if c.id == collection_id), None)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # Move all cameras in this collection to default
        cameras = service._load_cameras()
        for camera in cameras:
            if camera.collection_id == collection_id:
                camera.collection_id = "default"
                camera.collection_name = "Default Collection"
        service._save_cameras(cameras)
        
        # Remove the collection
        collections = [c for c in collections if c.id != collection_id]
        service._save_collections(collections)
        
        # Update collection counts
        service._update_collection_counts()
        
        return {"success": True, "message": f"Collection '{collection.name}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting collection: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete collection")

# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "camera_management"}
