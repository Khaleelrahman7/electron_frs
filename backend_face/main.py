from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create main FastAPI app
app = FastAPI(
    title="Face Recognition System API",
    description="Unified API for face recognition, camera management, registration, and video processing",
    version="1.0.0"
)

# Configure CORS to allow frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount individual service applications
def mount_services():
    """Mount all service applications"""

    # Mount event service
    try:
        from event.event_api import router as event_router
        app.include_router(event_router, prefix="/api/events", tags=["Events"])
        logger.info("✓ Event service mounted")
    except Exception as e:
        logger.error(f"✗ Failed to mount event service: {e}")

    # Old camera service removed - using enhanced camera management instead
    # Add a basic status endpoint
    @app.get("/api/status", tags=["System"])
    async def get_basic_status():
        """Get basic service status"""
        return {
            "status": "running",
            "camera_service": "enhanced",
            "message": "Using enhanced camera management system"
        }

    # Mount registration service
    try:
        from registration.reg import app as registration_app
        app.mount("/api/registration", registration_app)
        logger.info("✓ Registration service mounted")
    except Exception as e:
        logger.error(f"✗ Failed to mount registration service: {e}")

    # Mount enhanced camera management service
    try:
        from camera_management.routes import router as camera_management_router
        app.include_router(camera_management_router)
        logger.info("✓ Enhanced camera management service mounted")
    except Exception as e:
        logger.error(f"✗ Failed to mount enhanced camera management service: {e}")

    # Mount WebRTC streaming service
    try:
        from webrtc_streaming.routes import router as webrtc_router
        app.include_router(webrtc_router)
        logger.info("✓ WebRTC streaming service mounted")
    except Exception as e:
        logger.error(f"✗ Failed to mount WebRTC streaming service: {e}")
        logger.info("Continuing with basic camera service only")

    # Mount matching service
    try:
        from matching.one import app as matching_app
        app.mount("/api/matching", matching_app)
        logger.info("✓ Matching service mounted")
    except Exception as e:
        logger.error(f"✗ Failed to mount matching service: {e}")

    # Mount video processing service
    try:
        from video.video_thread import app as video_app
        app.mount("/api/video", video_app)
        logger.info("✓ Video processing service mounted")
    except Exception as e:
        logger.error(f"✗ Failed to mount video processing service: {e}")
        logger.info("Adding basic video endpoints as fallback")

        # Add basic video endpoints as fallback
        from fastapi import UploadFile, File, HTTPException
        import os
        import uuid
        from datetime import datetime

        @app.get("/api/video/formats")
        async def get_video_formats():
            """Get supported video formats"""
            return {
                "formats": ['.mp4', '.avi', '.mov', '.mkv', '.wmv'],
                "max_size": 1024 * 1024 * 100  # 100MB
            }

        @app.post("/api/video/upload")
        async def upload_video_fallback(file: UploadFile = File(...)):
            """Basic video upload endpoint"""
            try:
                # Check file format
                file_ext = os.path.splitext(file.filename)[1].lower()
                if file_ext not in ['.mp4', '.avi', '.mov', '.mkv', '.wmv']:
                    raise HTTPException(
                        status_code=400,
                        detail="Unsupported file format"
                    )

                # Generate file ID
                file_id = str(uuid.uuid4())

                return {
                    "filename": file_id,
                    "size": file.size if hasattr(file, 'size') else 0,
                    "format": file_ext,
                    "status": "uploaded",
                    "message": "Video uploaded successfully. Processing service is currently unavailable."
                }
            except Exception as e:
                logger.error(f"Video upload error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

# Mount all services
mount_services()

# Configure static file serving for gallery images and captured faces
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
GALLERY_DIR = os.path.join(DATA_DIR, "gallery")
CAPTURED_FACES_DIR = os.path.join(BASE_DIR, "captured_faces")

# Create directories if they don't exist
os.makedirs(GALLERY_DIR, exist_ok=True)
os.makedirs(CAPTURED_FACES_DIR, exist_ok=True)

# Mount static files for gallery images and captured faces
app.mount("/static/gallery", StaticFiles(directory=GALLERY_DIR), name="gallery")
app.mount("/static/captured", StaticFiles(directory=CAPTURED_FACES_DIR), name="captured")

# Add endpoint to serve gallery images with error handling
from fastapi import HTTPException
from fastapi.responses import FileResponse

@app.get("/api/gallery/image/{person_name}/{image_name}")
async def get_gallery_image(person_name: str, image_name: str):
    """Serve gallery images with proper error handling and fallback"""
    try:
        # Sanitize the inputs to prevent directory traversal
        person_name = person_name.replace('..', '').replace('/', '').replace('\\', '')
        image_name = image_name.replace('..', '').replace('/', '').replace('\\', '')

        # Construct the image path
        image_path = os.path.join(GALLERY_DIR, person_name, image_name)

        # Check if file exists and is within the gallery directory
        if not os.path.exists(image_path):
            # Try fallback images if the requested image doesn't exist
            fallback_names = ['1.jpg', 'original.jpg']
            if image_name not in fallback_names:
                for fallback_name in fallback_names:
                    fallback_path = os.path.join(GALLERY_DIR, person_name, fallback_name)
                    if os.path.exists(fallback_path):
                        image_path = fallback_path
                        logger.info(f"Using fallback image {fallback_name} for {person_name}/{image_name}")
                        break
                else:
                    raise HTTPException(status_code=404, detail=f"Image not found: {person_name}/{image_name}")
            else:
                raise HTTPException(status_code=404, detail=f"Image not found: {person_name}/{image_name}")

        # Ensure the path is within the gallery directory (security check)
        if not os.path.abspath(image_path).startswith(os.path.abspath(GALLERY_DIR)):
            raise HTTPException(status_code=403, detail="Access denied")

        # Return the image file
        return FileResponse(
            image_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving gallery image {person_name}/{image_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/captured/image/{face_type}/{camera}/{person}/{image_name}")
async def get_captured_image(face_type: str, camera: str, person: str, image_name: str):
    """Serve captured face images with proper error handling"""
    try:
        # Validate face_type
        if face_type not in ['known', 'unknown']:
            raise HTTPException(status_code=400, detail="Invalid face type. Must be 'known' or 'unknown'")

        # Sanitize the inputs to prevent directory traversal
        camera = camera.replace('..', '').replace('/', '').replace('\\', '')
        person = person.replace('..', '').replace('/', '').replace('\\', '')
        image_name = image_name.replace('..', '').replace('/', '').replace('\\', '')

        # Construct the image path
        image_path = os.path.join(CAPTURED_FACES_DIR, face_type, camera, person, image_name)

        # Check if file exists and is within the captured faces directory
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")

        # Ensure the path is within the captured faces directory (security check)
        if not os.path.abspath(image_path).startswith(os.path.abspath(CAPTURED_FACES_DIR)):
            raise HTTPException(status_code=403, detail="Access denied")

        # Return the image file
        return FileResponse(
            image_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving captured image {face_type}/{camera}/{person}/{image_name}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



@app.get("/", tags=["System"])
async def root():
    """Root endpoint"""
    return {
        "message": "Face Recognition System API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "events": "/api/events",
            "camera": "/api/camera",
            "registration": "/api/register",
            "matching": "/api/match",
            "video": "/api/video",
            "status": "/api/status",
            "health": "/api/health",
            "collections": "/api/collections"
        }
    }

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle OPTIONS requests for CORS preflight"""
    return {"message": "OK"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting unified Face Recognition System API on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)