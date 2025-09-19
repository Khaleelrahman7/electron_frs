import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException
import logging

from .models import (
    CameraCollection, EnhancedCamera, CameraCreateRequest, CameraUpdateRequest,
    CameraValidationRequest, CameraValidationResponse, CameraListResponse,
    CameraOperationResponse, extract_ip_from_url, validate_private_ip
)

logger = logging.getLogger(__name__)

class EnhancedCameraService:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.cameras_file = os.path.join(data_dir, "cameras.json")
        self.collections_file = os.path.join(data_dir, "collections.json")
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Initialize default collection
        self._ensure_default_collection()
    
    def _ensure_default_collection(self):
        """Ensure default collection exists"""
        collections = self._load_collections()
        if not any(c.id == "default" for c in collections):
            default_collection = CameraCollection(
                id="default",
                name="Default Collection",
                description="Default camera collection",
                created_at=datetime.now(),
                camera_count=0
            )
            collections.append(default_collection)
            self._save_collections(collections)
    
    def _load_cameras(self) -> List[EnhancedCamera]:
        """Load cameras from file"""
        try:
            if os.path.exists(self.cameras_file):
                with open(self.cameras_file, 'r') as f:
                    data = json.load(f)
                    return [EnhancedCamera(**camera) for camera in data]
            return []
        except Exception as e:
            logger.error(f"Error loading cameras: {e}")
            return []
    
    def _save_cameras(self, cameras: List[EnhancedCamera]):
        """Save cameras to file"""
        try:
            with open(self.cameras_file, 'w') as f:
                json.dump([camera.dict() for camera in cameras], f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving cameras: {e}")
            raise HTTPException(status_code=500, detail="Failed to save camera data")
    
    def _load_collections(self) -> List[CameraCollection]:
        """Load collections from file"""
        try:
            if os.path.exists(self.collections_file):
                with open(self.collections_file, 'r') as f:
                    data = json.load(f)
                    return [CameraCollection(**collection) for collection in data]
            return []
        except Exception as e:
            logger.error(f"Error loading collections: {e}")
            return []
    
    def _save_collections(self, collections: List[CameraCollection]):
        """Save collections to file"""
        try:
            with open(self.collections_file, 'w') as f:
                json.dump([collection.dict() for collection in collections], f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving collections: {e}")
            raise HTTPException(status_code=500, detail="Failed to save collection data")
    
    def _update_collection_counts(self):
        """Update camera counts for all collections"""
        cameras = self._load_cameras()
        collections = self._load_collections()
        
        # Count cameras per collection
        collection_counts = {}
        for camera in cameras:
            collection_id = camera.collection_id or "default"
            collection_counts[collection_id] = collection_counts.get(collection_id, 0) + 1
        
        # Update collection camera counts
        for collection in collections:
            collection.camera_count = collection_counts.get(collection.id, 0)
        
        self._save_collections(collections)
    
    def validate_camera(self, request: CameraValidationRequest) -> CameraValidationResponse:
        """Validate camera data including duplicate checking"""
        try:
            # Validate IP format
            ip_validation = validate_private_ip(request.ip)
            if not ip_validation["isValid"]:
                return CameraValidationResponse(
                    valid=False,
                    error=ip_validation["message"],
                    type="ip_validation"
                )
            
            # Check for duplicate IP (excluding specified IP if editing)
            cameras = self._load_cameras()
            for camera in cameras:
                camera_ip = extract_ip_from_url(camera.rtsp_url)
                if camera_ip == request.ip and camera_ip != request.exclude_ip:
                    collections = self._load_collections()
                    existing_collection = next(
                        (c.name for c in collections if c.id == camera.collection_id),
                        "Unknown Collection"
                    )
                    return CameraValidationResponse(
                        valid=False,
                        error=f"A camera with IP {request.ip} already exists",
                        type="duplicate",
                        existingCollection=existing_collection
                    )
            
            return CameraValidationResponse(valid=True)
            
        except Exception as e:
            logger.error(f"Error validating camera: {e}")
            return CameraValidationResponse(
                valid=False,
                error="Validation failed. Please try again.",
                type="server_error"
            )
    
    def create_camera(self, request: CameraCreateRequest) -> CameraOperationResponse:
        """Create a new camera"""
        try:
            cameras = self._load_cameras()
            
            # Generate new ID
            new_id = max([c.id for c in cameras], default=0) + 1
            
            # Extract IP for validation
            ip_address = extract_ip_from_url(request.rtsp_url)
            if not ip_address:
                raise HTTPException(status_code=400, detail="Could not extract IP from stream URL")
            
            # Validate for duplicates
            validation_request = CameraValidationRequest(
                ip=ip_address,
                streamUrl=request.rtsp_url,
                collection_name=request.collection_id
            )
            validation = self.validate_camera(validation_request)
            if not validation.valid:
                raise HTTPException(status_code=409, detail=validation.error)
            
            # Get collection name
            collections = self._load_collections()
            collection_name = None
            if request.collection_id:
                collection = next((c for c in collections if c.id == request.collection_id), None)
                collection_name = collection.name if collection else None
            
            # Create camera
            new_camera = EnhancedCamera(
                id=new_id,
                name=request.name,
                rtsp_url=request.rtsp_url,
                collection_id=request.collection_id or "default",
                collection_name=collection_name or "Default Collection",
                ip_address=ip_address,
                status="inactive",
                created_at=datetime.now(),
                error_count=0,
                is_active=False
            )
            
            cameras.append(new_camera)
            self._save_cameras(cameras)
            self._update_collection_counts()
            
            return CameraOperationResponse(
                success=True,
                message=f"Camera '{request.name}' added successfully",
                camera=new_camera
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating camera: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create camera: {str(e)}")
    
    def get_cameras(self, page: int = 1, per_page: int = 6) -> CameraListResponse:
        """Get paginated list of cameras with collections"""
        try:
            cameras = self._load_cameras()
            collections = self._load_collections()
            
            # Calculate pagination
            total_cameras = len(cameras)
            total_pages = max(1, (total_cameras + per_page - 1) // per_page)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            
            paginated_cameras = cameras[start_idx:end_idx]
            active_cameras = sum(1 for c in cameras if c.is_active)
            
            return CameraListResponse(
                cameras=paginated_cameras,
                collections=collections,
                total_cameras=total_cameras,
                active_cameras=active_cameras,
                current_page=page,
                total_pages=total_pages,
                cameras_per_page=per_page
            )

        except Exception as e:
            logger.error(f"Error getting cameras: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve cameras")

    def activate_camera(self, camera_id: int) -> CameraOperationResponse:
        """Activate a camera and start its stream"""
        try:
            cameras = self._load_cameras()
            camera = next((c for c in cameras if c.id == camera_id), None)

            if not camera:
                raise HTTPException(status_code=404, detail="Camera not found")

            # Update camera status
            camera.is_active = True
            camera.status = "active"
            camera.last_seen = datetime.now()

            # Save updated cameras
            self._save_cameras(cameras)

            # Also try to start the stream for this camera
            try:
                from .streaming import get_stream_manager
                stream_manager = get_stream_manager()

                # Check if stream already exists
                existing_stream = stream_manager.get_camera_stream(camera_id)
                if not existing_stream:
                    # Start new stream
                    stream_id = stream_manager.start_stream(camera_id, camera.rtsp_url)
                    logger.info(f"Started stream {stream_id} for activated camera {camera_id}")
                else:
                    logger.info(f"Stream already exists for camera {camera_id}: {existing_stream}")
            except Exception as stream_error:
                logger.warning(f"Failed to start stream for camera {camera_id}: {stream_error}")
                # Don't fail the activation if stream start fails

            return CameraOperationResponse(
                success=True,
                message=f"Camera '{camera.name}' activated successfully",
                camera=camera
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error activating camera {camera_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to activate camera")

    def deactivate_camera(self, camera_id: int) -> CameraOperationResponse:
        """Deactivate a camera"""
        try:
            cameras = self._load_cameras()
            camera = next((c for c in cameras if c.id == camera_id), None)

            if not camera:
                raise HTTPException(status_code=404, detail="Camera not found")

            # Update camera status
            camera.is_active = False
            camera.status = "inactive"

            # Save updated cameras
            self._save_cameras(cameras)

            return CameraOperationResponse(
                success=True,
                message=f"Camera '{camera.name}' deactivated successfully",
                camera=camera
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deactivating camera {camera_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to deactivate camera")
    
    def update_camera(self, camera_id: int, request: CameraUpdateRequest) -> CameraOperationResponse:
        """Update an existing camera"""
        try:
            cameras = self._load_cameras()
            camera = next((c for c in cameras if c.id == camera_id), None)
            
            if not camera:
                raise HTTPException(status_code=404, detail="Camera not found")
            
            # Update fields if provided
            if request.name is not None:
                camera.name = request.name
            
            if request.rtsp_url is not None:
                # Validate new URL
                new_ip = extract_ip_from_url(request.rtsp_url)
                if new_ip:
                    validation_request = CameraValidationRequest(
                        ip=new_ip,
                        streamUrl=request.rtsp_url,
                        exclude_ip=camera.ip_address
                    )
                    validation = self.validate_camera(validation_request)
                    if not validation.valid:
                        raise HTTPException(status_code=409, detail=validation.error)
                
                camera.rtsp_url = request.rtsp_url
                camera.ip_address = new_ip
            
            if request.collection_id is not None:
                camera.collection_id = request.collection_id
                # Update collection name
                collections = self._load_collections()
                collection = next((c for c in collections if c.id == request.collection_id), None)
                camera.collection_name = collection.name if collection else "Unknown Collection"
            
            self._save_cameras(cameras)
            self._update_collection_counts()
            
            return CameraOperationResponse(
                success=True,
                message=f"Camera '{camera.name}' updated successfully",
                camera=camera
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating camera: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update camera: {str(e)}")
    
    def delete_camera(self, camera_id: int) -> CameraOperationResponse:
        """Delete a camera"""
        try:
            cameras = self._load_cameras()
            camera = next((c for c in cameras if c.id == camera_id), None)
            
            if not camera:
                raise HTTPException(status_code=404, detail="Camera not found")
            
            # Remove camera
            cameras = [c for c in cameras if c.id != camera_id]
            self._save_cameras(cameras)
            self._update_collection_counts()
            
            return CameraOperationResponse(
                success=True,
                message=f"Camera '{camera.name}' deleted successfully"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting camera: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to delete camera: {str(e)}")
