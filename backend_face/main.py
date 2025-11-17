from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
import logging
import os
import json
import uuid
import time
import cv2
import threading
from typing import Dict, Optional
from face_pipeline import init as init_face_pipeline, process_frame

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
FACE_PIPELINE_READY = False

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
# Initialize face pipeline (non-disruptive; skips if unavailable)
# Try GPU first (ctx=0), will auto-fallback to CPU if GPU unavailable
try:
    # Optimized for Tesla T4 GPU: Higher detection size for better accuracy
    # (1024, 1024) provides excellent quality while Tesla T4 can handle it efficiently
    init_face_pipeline(os.path.join(os.path.dirname(__file__), "data"), ctx=0, det_size=(1024, 1024))
    FACE_PIPELINE_READY = True
    logger.info("✓ Face pipeline initialized")
except Exception as e:
    FACE_PIPELINE_READY = False
    logger.error(f"✗ Face pipeline init failed: {e}")
    logger.info("Face recognition will be disabled. Check CUDA/GPU setup if GPU was expected.")

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

@app.get("/api/gallery/image/{person_name}/{image_name:path}")
async def get_gallery_image(person_name: str, image_name: str):
    """Serve gallery images with proper error handling and fallback"""
    try:
        # Sanitize the inputs to prevent directory traversal
        person_name = person_name.replace('..', '').replace('/', '').replace('\\', '')
        # Extract just the filename from image_name (in case full path is passed)
        image_name = os.path.basename(image_name)
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
        # Extract just the filename from image_name (in case full path is passed)
        image_name = os.path.basename(image_name)
        image_name = image_name.replace('..', '').replace('/', '').replace('\\', '')

        base_dir = os.path.join(CAPTURED_FACES_DIR, face_type)
        candidates = []

        if camera == "default":
            candidates.append(os.path.join(base_dir, image_name))
            if person and person not in ["default", "unknown"]:
                candidates.append(os.path.join(base_dir, person, image_name))
        else:
            candidates.append(os.path.join(base_dir, camera, person, image_name))
            candidates.append(os.path.join(base_dir, camera, image_name))
            if person and person not in ["default", "unknown"]:
                candidates.append(os.path.join(base_dir, person, image_name))

        image_path = next((path for path in candidates if os.path.exists(path)), None)

        if not image_path:
            raise HTTPException(status_code=404, detail="Image not found")

        if not os.path.abspath(image_path).startswith(os.path.abspath(CAPTURED_FACES_DIR)):
            raise HTTPException(status_code=403, detail="Access denied")

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
            "collections": "/api/collections",
            "capture": "/capture_face_upload or /capture_face_b64"
        }
    }

# ============= FACE CAPTURE ENDPOINTS =============

class CaptureBase64(BaseModel):
    """Pydantic model for base64 face capture requests"""
    image_b64: str
    label: str = "unknown"
    confidence: Optional[float] = None

@app.post("/capture_face_upload", tags=["Face Capture"])
async def capture_face_upload(file: UploadFile = File(...), label: str = Form("unknown"), confidence: float = Form(None)):
    """
    Upload a face image file and save it to captured_faces.
    
    Parameters:
    - file: JPEG/PNG image file
    - label: Person name/label for the face (default: "unknown")
    - confidence: Optional confidence score (0.0-1.0)
    """
    try:
        from save_face import save_face_image
        import numpy as np
        
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        saved = save_face_image(img, label, confidence=confidence, source="upload")
        
        return {
            "saved": bool(saved),
            "path": str(saved) if saved else None,
            "label": label,
            "source": "upload"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading face image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save face: {str(e)}")

@app.post("/capture_face_b64", tags=["Face Capture"])
async def capture_face_b64(payload: CaptureBase64):
    """
    Capture face from base64 encoded image (typically from frontend video element).
    
    JSON payload:
    {
        "image_b64": "data:image/jpeg;base64,...",
        "label": "person_name",
        "confidence": 0.95
    }
    """
    try:
        from save_face import save_face_image
        import base64
        import numpy as np
        
        image_b64 = payload.image_b64
        label = payload.label
        confidence = payload.confidence
        
        if not image_b64:
            raise HTTPException(status_code=400, detail="No image_b64 provided")
        
        # Handle data URL prefix (e.g., "data:image/jpeg;base64,...")
        header, data = (image_b64.split(",", 1) if "," in image_b64 else (None, image_b64))
        img_data = base64.b64decode(data)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image format")
        
        saved = save_face_image(img, label, confidence=confidence, source="upload")
        
        return {
            "saved": bool(saved),
            "path": str(saved) if saved else None,
            "label": label,
            "source": "upload_b64"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error capturing face from base64: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save face: {str(e)}")

# Simple stream management for compatibility with working implementation
active_streams: Dict[str, Dict] = {}
stream_lock = threading.Lock()

class SimpleRTSPStream:
    """Simple RTSP stream handler for MJPEG streaming"""

    def __init__(self, rtsp_url: str, stream_id: str):
        self.rtsp_url = rtsp_url
        self.stream_id = stream_id
        self.cap = None
        self.is_running = False
        self.lock = threading.Lock()
        self.last_frame = None
        self.thread = None

    def start(self):
        """Start the RTSP stream capture in a separate thread"""
        with self.lock:
            if self.is_running:
                return

            self.is_running = True
            self.thread = threading.Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            logger.info(f"Started RTSP stream for {self.rtsp_url}")

    def stop(self):
        """Stop the RTSP stream capture"""
        with self.lock:
            self.is_running = False
            if self.cap:
                self.cap.release()
                self.cap = None
            logger.info(f"Stopped RTSP stream for {self.rtsp_url}")

    def _capture_frames(self):
        """Continuously capture frames from RTSP stream"""
        retry_count = 0
        max_retries = 5

        while self.is_running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    logger.info(f"Connecting to RTSP stream: {self.rtsp_url}")
                    # Handle camera index (0, 1, 2, etc.) vs RTSP URL
                    if isinstance(self.rtsp_url, str) and self.rtsp_url.isdigit():
                        import platform
                        # On Windows, use DirectShow for USB cameras to avoid MSMF errors
                        if platform.system() == 'Windows':
                            self.cap = cv2.VideoCapture(int(self.rtsp_url), cv2.CAP_DSHOW)
                        else:
                            self.cap = cv2.VideoCapture(int(self.rtsp_url))
                    else:
                        self.cap = cv2.VideoCapture(self.rtsp_url)

                    if self.cap.isOpened():
                        # Optimized for Tesla T4: High quality capture settings
                        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffering for low latency
                        self.cap.set(cv2.CAP_PROP_FPS, 30)  # Higher FPS for smoother streams
                        # Maximize resolution for Tesla T4
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                        logger.info(f"Successfully connected to RTSP stream")
                        retry_count = 0
                    else:
                        raise Exception("Failed to open camera")

                # Read frame
                ret, frame = self.cap.read()

                if ret and frame is not None and frame.size > 0:
                    with self.lock:
                        self.last_frame = frame.copy()
                    retry_count = 0
                else:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"Too many consecutive failures for stream {self.stream_id}")
                        if self.cap:
                            self.cap.release()
                            self.cap = None
                        time.sleep(2)
                        retry_count = 0
                        continue

                # Control frame rate
                time.sleep(0.04)  # ~25 FPS

            except Exception as e:
                logger.error(f"Error in RTSP capture for {self.rtsp_url}: {e}")
                if self.cap:
                    self.cap.release()
                    self.cap = None
                time.sleep(2)

    def get_frame(self) -> Optional[bytes]:
        """Get the latest frame as JPEG bytes"""
        with self.lock:
            if self.last_frame is not None:
                try:
                    # Optimized for Tesla T4: Encode frame as JPEG with maximum quality
                    _, buffer = cv2.imencode('.jpg', self.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    return buffer.tobytes()
                except Exception as e:
                    logger.error(f"Error encoding frame: {e}")
                    return None
            return None

def generate_mjpeg_stream(stream_id: str):
    """Generate MJPEG stream for a given stream ID"""
    if stream_id not in active_streams:
        logger.error(f"Stream {stream_id} not found")
        return

    stream = active_streams[stream_id]['stream']
    logger.info(f"Starting MJPEG stream generation for {stream_id}")

    try:
        while True:
            # Prefer raw frame for processing if pipeline ready
            frame = None
            if FACE_PIPELINE_READY:
                try:
                    with stream.lock:
                        frame = stream.last_frame.copy() if getattr(stream, 'last_frame', None) is not None else None
                except Exception:
                    frame = None

            if frame is not None:
                try:
                    processed_frame, _ = process_frame(frame)
                except Exception as e:
                    logger.debug(f"Face pipeline processing error for {stream_id}: {e}")
                    processed_frame = frame
                try:
                    _, buffer = cv2.imencode('.jpg', processed_frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                except Exception as e:
                    logger.error(f"Error encoding processed frame for {stream_id}: {e}")
                    time.sleep(0.033)
                continue

            # Fallback: use existing encoded frame path (no changes to behavior)
            frame_data = stream.get_frame()
            if frame_data:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            else:
                # Send a small delay if no frame is available
                time.sleep(0.033)  # ~30 FPS
    except Exception as e:
        logger.error(f"Error in MJPEG stream generation for {stream_id}: {e}")
        return

@app.get("/api/video_feed/{stream_id}")
async def video_feed(stream_id: str):
    """Serve MJPEG video feed for a specific stream"""
    logger.info(f"Video feed requested for stream: {stream_id}")

    if stream_id not in active_streams:
        logger.error(f"Stream {stream_id} not found in active streams")
        return JSONResponse({"error": "Stream not found"}, status_code=404)

    stream = active_streams[stream_id]['stream']
    if not stream.is_running:
        logger.error(f"Stream {stream_id} is not running")
        return JSONResponse({"error": "Stream not running"}, status_code=404)

    logger.info(f"Serving MJPEG video feed for stream: {stream_id}")
    return StreamingResponse(
        generate_mjpeg_stream(stream_id),
        media_type='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        }
    )

@app.get("/api/get_stream_for_camera")
async def get_stream_for_camera(camera_ip: str, collection_name: str = None):
    """Get existing stream information for a camera"""
    try:
        # Generate consistent stream ID
        if not collection_name:
            collection_name = 'default'

        consistent_stream_id = f"{collection_name}_{camera_ip}"

        # Check if stream already exists
        if consistent_stream_id in active_streams:
            existing_stream = active_streams[consistent_stream_id]
            if existing_stream['stream'].is_running:
                return JSONResponse({
                    "success": True,
                    "stream_id": consistent_stream_id,
                    "feed_url": f"/api/video_feed/{consistent_stream_id}",
                    "exists": True,
                    "is_running": True
                })

        return JSONResponse({
            "success": True,
            "stream_id": consistent_stream_id,
            "feed_url": f"/api/video_feed/{consistent_stream_id}",
            "exists": False,
            "is_running": False
        })

    except Exception as e:
        logger.error(f"Error getting stream for camera: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/start_stream")
async def start_stream(request: Request):
    """Start a new RTSP stream"""
    try:
        body = await request.json()
        rtsp_url = body.get("rtsp_url")
        stream_id = body.get("stream_id")

        if not rtsp_url or not stream_id:
            return JSONResponse({"error": "rtsp_url and stream_id are required"}, status_code=400)

        # Check if stream already exists and is running
        if stream_id in active_streams:
            existing_stream = active_streams[stream_id]
            if existing_stream['stream'].is_running and existing_stream['rtsp_url'] == rtsp_url:
                logger.debug(f"Stream {stream_id} already exists and running, reusing...")
                return JSONResponse({
                    "success": True,
                    "stream_id": stream_id,
                    "feed_url": f"/api/video_feed/{stream_id}",
                    "reused": True
                })
            else:
                # Stop existing stream if URL is different or not running
                logger.info(f"Stopping existing stream {stream_id}")
                existing_stream['stream'].stop()
                del active_streams[stream_id]

        # Create new stream
        logger.info(f"Creating new stream {stream_id} for URL: {rtsp_url}")
        stream = SimpleRTSPStream(rtsp_url, stream_id)
        stream.start()

        active_streams[stream_id] = {
            'stream': stream,
            'rtsp_url': rtsp_url,
            'created_at': time.time()
        }

        logger.info(f"Started stream {stream_id} for URL: {rtsp_url}")

        return JSONResponse({
            "success": True,
            "stream_id": stream_id,
            "feed_url": f"/api/video_feed/{stream_id}"
        })

    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.delete("/api/stop_stream/{stream_id}")
async def stop_stream(stream_id: str):
    """Stop a specific stream"""
    try:
        if stream_id in active_streams:
            active_streams[stream_id]['stream'].stop()
            del active_streams[stream_id]
            logger.info(f"Stopped stream {stream_id}")
            return JSONResponse({"success": True, "message": f"Stream {stream_id} stopped"})
        else:
            return JSONResponse({"error": "Stream not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error stopping stream {stream_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle OPTIONS requests for CORS preflight"""
    return {"message": "OK"}

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting unified Face Recognition System API on port 8005")
    uvicorn.run(app, host="0.0.0.0", port=8005)