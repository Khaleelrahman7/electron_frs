from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
import json
import os
import atexit
import shutil
import logging
import time
import cv2
import threading
import asyncio
import signal
from typing import Dict, Optional
from routes import analytics, users, events, camera_rules, collections, webrtc, augment, archive, dashboard_analytics, appearance_search
import camera_settings
from archive_manager import ArchiveRecordingManager
from fastapi import status
import uvicorn
import webrtc_signaling

# Set up logging first
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import stream configuration
try:
    from config.stream_config import stream_config
    logger_config_msg = "Using custom stream configuration"
except ImportError:
    # Fallback configuration if config file is not available
    class FallbackConfig:
        RTSP_OPEN_TIMEOUT = 45
        RTSP_READ_TIMEOUT = 90
        MAX_RECONNECT_ATTEMPTS = 10
        MAX_FRAME_RETRIES = 5
        FRAME_TIMEOUT_THRESHOLD = 60
        BUFFER_SIZE_STABLE = 3
        TARGET_FPS_STABLE = 25
        HEALTH_CHECK_INTERVAL = 30
        CONNECTION_TEST_FRAMES = 5
        MIN_SUCCESSFUL_TEST_FRAMES = 3
        TIMEOUT_ERROR_DELAY = 15
        GENERAL_ERROR_DELAY = 30
        CRITICAL_ERROR_DELAY = 300

        CONNECTION_METHODS = [
            {'name': 'TCP', 'url_suffix': '?tcp', 'timeout_open_ms': 45000, 'timeout_read_ms': 90000, 'buffer_size': 3},
            {'name': 'Original', 'url_suffix': '', 'timeout_open_ms': 35000, 'timeout_read_ms': 75000, 'buffer_size': 2},
            {'name': 'TCP Max', 'url_suffix': '', 'timeout_open_ms': 45000, 'timeout_read_ms': 90000, 'buffer_size': 4},
            {'name': 'UDP', 'url_suffix': '?udp', 'timeout_open_ms': 25000, 'timeout_read_ms': 60000, 'buffer_size': 2}
        ]

    stream_config = FallbackConfig()
    logger_config_msg = "Using fallback stream configuration"

# Import stream monitoring
try:
    from stream_monitor import stream_monitor, get_stream_diagnostics
    monitor_available = True
except ImportError:
    monitor_available = False
    logger.warning("Stream monitoring not available")

logger.info(logger_config_msg)

class RTSPStream:
    """Thread-safe RTSP stream handler for MJPEG streaming"""

    def __init__(self, rtsp_url: str, stream_id: str = None):
        self.rtsp_url = rtsp_url
        self.stream_id = stream_id or f"stream_{int(time.time())}"
        self.cap = None
        self.is_running = False
        self.lock = threading.Lock()
        self.last_frame = None
        self.thread = None

        # Register with monitor if available
        if monitor_available:
            stream_monitor.register_stream(self.stream_id, rtsp_url)

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
        """Continuously capture frames from RTSP stream with improved stability"""
        retry_count = 0
        max_retries = 5  # Increased from 3
        reconnect_attempts = 0
        max_reconnect_attempts = 10
        last_successful_frame_time = time.time()
        connection_health_check_interval = 30  # Check connection health every 30 seconds
        last_health_check = time.time()

        while self.is_running:
            try:
                if self.cap is None or not self.cap.isOpened():
                    logger.info(f"Connecting to RTSP stream: {self.rtsp_url}")

                    # Exponential backoff for reconnection attempts
                    if reconnect_attempts > 0:
                        backoff_delay = min(2 ** reconnect_attempts, 60)  # Max 60 seconds
                        logger.info(f"Waiting {backoff_delay} seconds before reconnection attempt {reconnect_attempts + 1}")
                        time.sleep(backoff_delay)

                    # Try different connection methods with improved timeout settings
                    connection_methods = [
                        # Method 1: TCP transport with extended timeouts
                        {
                            'url': f"{self.rtsp_url}?tcp",
                            'timeout_open': 45000,  # 45 seconds - increased from 30000
                            'timeout_read': 120000,  # 120 seconds - increased from 60000
                            'buffer_size': 3,
                            'name': 'TCP with extended timeouts'
                        },
                        # Method 2: Original URL with standard timeouts
                        {
                            'url': self.rtsp_url,
                            'timeout_open': 35000,  # 35 seconds
                            'timeout_read': 90000,  # 90 seconds - increased from 45000
                            'buffer_size': 2,
                            'name': 'Original URL with standard timeouts'
                        },
                        # Method 3: TCP with maximum timeouts and larger buffer
                        {
                            'url': self.rtsp_url,
                            'timeout_open': 60000,  # 60 seconds - increased from 45000
                            'timeout_read': 180000,  # 180 seconds - increased from 90000
                            'buffer_size': 5,  # Larger buffer for stability
                            'name': 'TCP with maximum timeouts'
                        },
                        # Method 4: UDP fallback with moderate timeouts
                        {
                            'url': f"{self.rtsp_url}?udp",
                            'timeout_open': 25000,  # 25 seconds
                            'timeout_read': 60000,  # 60 seconds - increased from 30000
                            'buffer_size': 2,
                            'name': 'UDP fallback'
                        }
                    ]

                    connection_successful = False
                    for i, method in enumerate(connection_methods):
                        try:
                            method_name = method.get('name', f"Method {i+1}")
                            logger.info(f"Trying {method_name}: {method['url']} (open: {method['timeout_open']/1000}s, read: {method['timeout_read']/1000}s)")

                            # Create VideoCapture with timeout handling
                            self.cap = cv2.VideoCapture(method['url'])

                            # Set timeouts and buffer settings with error handling
                            try:
                                self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, method['timeout_open'])
                                self.cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, method['timeout_read'])
                                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, method['buffer_size'])

                                # Additional stability settings
                                self.cap.set(cv2.CAP_PROP_FPS, 25)  # Set to 25 FPS for stability

                                # Try to set codec preferences if available
                                try:
                                    self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('H', '2', '6', '4'))
                                except:
                                    pass  # Ignore if not supported

                                # Set additional properties for better stability
                                try:
                                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
                                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
                                except:
                                    pass  # Ignore if not supported

                            except Exception as prop_error:
                                logger.warning(f"Failed to set some capture properties: {prop_error}")
                                # Continue anyway as basic capture might still work

                            # Test if connection works with multiple frame reads
                            if self.cap.isOpened():
                                # Try to read multiple frames to ensure stable connection
                                test_frames_count = 0
                                for _ in range(5):  # Test with 5 frames
                                    test_ret, test_frame = self.cap.read()
                                    if test_ret and test_frame is not None:
                                        test_frames_count += 1
                                        with self.lock:
                                            self.last_frame = test_frame
                                    time.sleep(0.1)  # Small delay between test reads

                                if test_frames_count >= 3:  # At least 3 successful frames
                                    logger.info(f"✅ Successfully connected using {method_name}: {method['url']} ({test_frames_count}/5 test frames)")
                                    connection_successful = True
                                    reconnect_attempts = 0  # Reset reconnect counter on success
                                    last_successful_frame_time = time.time()

                                    # Update monitoring
                                    if monitor_available:
                                        stream_monitor.update_connection_attempt(self.stream_id, success=True)
                                    break
                                else:
                                    logger.warning(f"❌ {method_name} unstable: only {test_frames_count}/5 test frames successful")
                                    self.cap.release()
                                    self.cap = None
                            else:
                                logger.warning(f"❌ {method_name} failed to open stream")
                                self.cap.release()
                                self.cap = None

                        except Exception as method_error:
                            error_msg = str(method_error).lower()
                            if 'timeout' in error_msg:
                                logger.warning(f"⏱️ {method_name} timed out: {method_error}")
                            else:
                                logger.warning(f"❌ {method_name} failed: {method_error}")
                            if self.cap:
                                self.cap.release()
                                self.cap = None
                            continue

                    if not connection_successful:
                        reconnect_attempts += 1
                        if reconnect_attempts >= max_reconnect_attempts:
                            logger.error(f"Max reconnection attempts ({max_reconnect_attempts}) reached for {self.rtsp_url}")
                            time.sleep(300)  # Wait 5 minutes before trying again
                            reconnect_attempts = 0
                        raise Exception("All connection methods failed")

                # Main frame capture loop
                ret, frame = self.cap.read()
                current_time = time.time()

                if ret and frame is not None:
                    with self.lock:
                        self.last_frame = frame
                    retry_count = 0
                    last_successful_frame_time = current_time

                    # Update monitoring
                    if monitor_available:
                        stream_monitor.update_frame_received(self.stream_id)

                    # Adaptive frame rate based on connection stability
                    if current_time - last_successful_frame_time < 10:
                        time.sleep(0.04)  # 25 FPS for stable connections
                    else:
                        time.sleep(0.067)  # 15 FPS for less stable connections
                else:
                    logger.warning(f"Failed to read frame from {self.rtsp_url}")
                    retry_count += 1

                    # Check if we've been without frames for too long
                    if current_time - last_successful_frame_time > 60:  # 60 seconds without frames
                        logger.error(f"No frames received for 60 seconds from {self.rtsp_url}, forcing reconnection")
                        if self.cap:
                            self.cap.release()
                            self.cap = None
                        retry_count = 0
                        continue

                    if retry_count >= max_retries:
                        logger.error(f"Max retries reached for {self.rtsp_url}, reconnecting...")
                        if self.cap:
                            self.cap.release()
                            self.cap = None
                        retry_count = 0
                        time.sleep(5)  # Wait before reconnecting
                    else:
                        time.sleep(min(retry_count * 2, 10))  # Progressive delay

                # Periodic connection health check
                if current_time - last_health_check > connection_health_check_interval:
                    if self.cap and self.cap.isOpened():
                        # Try to get stream properties to check if connection is still alive
                        try:
                            fps = self.cap.get(cv2.CAP_PROP_FPS)
                            if fps <= 0:  # Invalid FPS might indicate connection issues
                                logger.warning(f"Connection health check failed for {self.rtsp_url} (invalid FPS: {fps})")
                        except:
                            logger.warning(f"Connection health check failed for {self.rtsp_url}")
                    last_health_check = current_time

            except Exception as e:
                error_msg = str(e).lower()
                error_type = 'general'

                if 'hevc' in error_msg or 'h.265' in error_msg or 'cabac' in error_msg or 'cu_qp_delta' in error_msg:
                    logger.warning(f"🎥 HEVC/H.265 codec issue for {self.rtsp_url}: {e}")
                    logger.info("🔄 Attempting to reconnect with different codec settings...")
                    error_type = 'codec'
                elif 'timeout' in error_msg or 'stream timeout triggered' in error_msg:
                    logger.warning(f"⏱️ Stream timeout for {self.rtsp_url} (will retry with longer timeouts): {e}")
                    error_type = 'timeout'
                elif 'connection' in error_msg or 'network' in error_msg:
                    logger.warning(f"🌐 Network connection issue for {self.rtsp_url}: {e}")
                    error_type = 'network'
                elif 'authentication' in error_msg or 'unauthorized' in error_msg:
                    logger.error(f"🔐 Authentication failed for {self.rtsp_url}: {e}")
                    error_type = 'auth'
                else:
                    logger.error(f"❌ General error in RTSP capture for {self.rtsp_url}: {e}")

                # Update monitoring
                if monitor_available:
                    stream_monitor.update_error(self.stream_id, str(e), error_type)

                if self.cap:
                    self.cap.release()
                    self.cap = None

                # Progressive delay based on error type
                if error_type == 'timeout':
                    time.sleep(10)  # Shorter wait for timeout errors - will try with longer timeouts
                elif error_type == 'network':
                    time.sleep(20)  # Medium wait for network issues
                elif error_type == 'auth':
                    time.sleep(60)  # Longer wait for auth issues (likely persistent)
                else:
                    time.sleep(30)  # Standard wait for other errors

    def get_frame(self) -> Optional[bytes]:
        """Get the latest frame as JPEG bytes"""
        with self.lock:
            if self.last_frame is not None:
                try:
                    # Encode frame as JPEG
                    _, buffer = cv2.imencode('.jpg', self.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    return buffer.tobytes()
                except Exception as e:
                    logger.error(f"Error encoding frame: {e}")
                    return None
            return None

# Global dictionary to store active RTSP streams
active_streams: Dict[str, RTSPStream] = {}

# Global archive recording manager
archive_recording_manager: Optional[ArchiveRecordingManager] = None

# Health check task
health_check_task = None

async def periodic_health_check():
    """Periodic health check for recording processes"""
    global archive_recording_manager

    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes

            if archive_recording_manager:
                logger.info("Running periodic recording health check...")
                archive_recording_manager.restart_failed_recordings()

                # Log current status
                status = archive_recording_manager.get_recording_status()
                active_count = status.get('active_recordings', 0)
                logger.info(f"Health check complete: {active_count} active recordings")

        except Exception as e:
            logger.error(f"Error in periodic health check: {e}")

def start_health_check_task():
    """Start the periodic health check task"""
    global health_check_task

    if health_check_task is None:
        health_check_task = asyncio.create_task(periodic_health_check())
        logger.info("Started periodic health check task")

app = FastAPI(title="VMS RTSP Streaming Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event to auto-start all configured camera streams
@app.on_event("startup")
async def startup_event():
    """Auto-start all configured camera streams and archive recording when the server starts"""
    global archive_recording_manager

    logger.info("Starting VMS RTSP Streaming Server...")

    # Initialize archive recording manager
    try:
        archive_recording_manager = ArchiveRecordingManager(CAMERA_JSON_PATH, "./recordings")
        # Set the archive manager in the archive routes module
        archive.set_archive_manager(archive_recording_manager)

        # Start recording for all configured cameras
        archive_recording_manager.start_all_recordings()
        logger.info("Archive recording system initialized and started")

        # Start periodic health check
        start_health_check_task()

    except Exception as e:
        logger.error(f"Failed to initialize archive recording system: {e}")
        # Try to continue without archive recording
        logger.warning("Continuing without archive recording functionality")

    logger.info("Auto-starting configured camera streams...")
    auto_start_all_streams()

# Shutdown event to ensure clean shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown of all recording processes and streams"""
    logger.info("FastAPI shutdown event triggered, cleaning up...")
    cleanup_streams()

# Get the backend directory
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
CAMERA_JSON_PATH = os.path.join(BACKEND_DIR, "data/camera_configuration.json")

# Log the paths for debugging
logger.debug(f"Backend directory: {BACKEND_DIR}")
logger.debug(f"Looking for camera config at: {CAMERA_JSON_PATH}")
logger.debug(f"File exists: {os.path.exists(CAMERA_JSON_PATH)}")

def cleanup_streams():
    """Clean up all active streams and archive recording"""
    global active_streams, archive_recording_manager

    # Stop all active streams
    for stream_id, stream in active_streams.items():
        try:
            stream.stop()
        except Exception as e:
            logger.error(f"Error stopping stream {stream_id}: {e}")
    active_streams.clear()
    logger.info("All streams cleaned up")

    # Stop archive recording
    if archive_recording_manager:
        try:
            archive_recording_manager.stop_all_recordings()
            logger.info("Archive recording stopped")
        except Exception as e:
            logger.error(f"Error stopping archive recording: {e}")

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    cleanup_streams()
    exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Register cleanup function
atexit.register(cleanup_streams)

def auto_start_all_streams():
    """Automatically start streams for all configured cameras on startup"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            logger.warning(f"Camera configuration file not found at: {CAMERA_JSON_PATH}")
            return

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        total_started = 0
        total_errors = 0

        for collection_name, cameras in camera_data.items():
            logger.info(f"Auto-starting streams for collection: {collection_name}")

            for camera_ip, rtsp_url in cameras.items():
                # Use consistent stream ID format: collection_cameraip
                stream_id = f"{collection_name}_{camera_ip}"

                try:
                    # Skip if stream already exists and is running
                    if stream_id in active_streams:
                        existing_stream = active_streams[stream_id]
                        if existing_stream.is_running and existing_stream.rtsp_url == rtsp_url:
                            logger.info(f"Stream {stream_id} already running, skipping...")
                            continue
                        else:
                            # Stop existing stream if URL changed or not running
                            existing_stream.stop()
                            del active_streams[stream_id]

                    # Create and start new stream
                    logger.info(f"Auto-starting stream {stream_id} for URL: {rtsp_url}")
                    stream = RTSPStream(rtsp_url, stream_id)
                    stream.start()
                    active_streams[stream_id] = stream
                    total_started += 1

                except Exception as e:
                    logger.error(f"Failed to auto-start stream for {camera_ip} in {collection_name}: {e}")
                    total_errors += 1

        logger.info(f"Auto-startup complete: {total_started} streams started, {total_errors} errors")

    except Exception as e:
        logger.error(f"Error during auto-startup of streams: {e}")

def generate_mjpeg_stream(stream_id: str):
    """Generate MJPEG stream for a given stream ID"""
    if stream_id not in active_streams:
        logger.error(f"Stream {stream_id} not found")
        return

    stream = active_streams[stream_id]

    while True:
        frame_data = stream.get_frame()
        if frame_data:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        else:
            # Send a small delay if no frame is available
            time.sleep(0.033)  # ~30 FPS

@app.get("/api/video_feed/{stream_id}")
async def video_feed(stream_id: str):
    """Serve MJPEG video feed for a specific stream"""
    if stream_id not in active_streams:
        return JSONResponse({"error": "Stream not found"}, status_code=404)

    return StreamingResponse(
        generate_mjpeg_stream(stream_id),
        media_type='multipart/x-mixed-replace; boundary=frame'
    )

@app.get("/api/get_stream_for_camera")
async def get_stream_for_camera(camera_ip: str, collection_name: str = None):
    """Get existing stream information for a camera, or suggest consistent stream ID"""
    try:
        # If collection_name not provided, try to find it in the configuration
        if not collection_name:
            if not os.path.exists(CAMERA_JSON_PATH):
                return JSONResponse({"error": "camera_configuration.json not found"}, status_code=404)

            with open(CAMERA_JSON_PATH, "r") as f:
                camera_data = json.load(f)

            # Find which collection contains this camera IP
            for coll_name, cameras in camera_data.items():
                if camera_ip in cameras:
                    collection_name = coll_name
                    break

            if not collection_name:
                return JSONResponse({"error": "Camera IP not found in any collection"}, status_code=404)

        # Generate consistent stream ID
        consistent_stream_id = f"{collection_name}_{camera_ip}"

        # Check if stream already exists
        if consistent_stream_id in active_streams:
            existing_stream = active_streams[consistent_stream_id]
            if existing_stream.is_running:
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
    """Start a new RTSP stream with improved existing stream handling"""
    try:
        body = await request.json()
        rtsp_url = body.get("rtsp_url")
        stream_id = body.get("stream_id")

        if not rtsp_url or not stream_id:
            return JSONResponse({"error": "rtsp_url and stream_id are required"}, status_code=400)

        # Check if stream already exists and is running
        if stream_id in active_streams:
            existing_stream = active_streams[stream_id]
            if existing_stream.is_running and existing_stream.rtsp_url == rtsp_url:
                logger.debug(f"Stream {stream_id} already exists and running, reusing...")
                return JSONResponse({
                    "success": True,
                    "stream_id": stream_id,
                    "feed_url": f"/api/video_feed/{stream_id}",
                    "reused": True
                })
            else:
                # Stop existing stream if URL is different or not running
                logger.info(f"Stopping existing stream {stream_id} (URL changed or not running)")
                existing_stream.stop()
                del active_streams[stream_id]

        # Only log new stream creation, not reuse
        logger.info(f"Creating new stream {stream_id} for URL: {rtsp_url}")
        stream = RTSPStream(rtsp_url, stream_id)
        stream.start()
        active_streams[stream_id] = stream

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
            active_streams[stream_id].stop()
            del active_streams[stream_id]
            logger.info(f"Stopped stream {stream_id}")
            return JSONResponse({"success": True, "message": f"Stream {stream_id} stopped"})
        else:
            return JSONResponse({"error": "Stream not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error stopping stream {stream_id}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/streams")
async def list_streams():
    """List all active streams"""
    try:
        stream_info = {}
        for stream_id, stream in active_streams.items():
            stream_info[stream_id] = {
                "rtsp_url": stream.rtsp_url,
                "is_running": stream.is_running,
                "feed_url": f"/api/video_feed/{stream_id}"
            }
        return JSONResponse({"streams": stream_info})
    except Exception as e:
        logger.error(f"Error listing streams: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Integration with existing camera configuration system
@app.get("/api/start_collection_streams/{collection_name}")
async def start_collection_streams(collection_name: str):
    """Start streams for all cameras in a collection"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return JSONResponse({"error": "camera_configuration.json not found"}, status_code=404)

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        if collection_name not in camera_data:
            return JSONResponse({"error": "Collection not found"}, status_code=404)

        started_streams = []
        errors = []

        for camera_ip, rtsp_url in camera_data[collection_name].items():
            stream_id = f"{collection_name}_{camera_ip}"

            try:
                # Stop existing stream if it exists
                if stream_id in active_streams:
                    active_streams[stream_id].stop()
                    del active_streams[stream_id]

                # Create and start new stream
                stream = RTSPStream(rtsp_url)
                stream.start()
                active_streams[stream_id] = stream

                started_streams.append({
                    "stream_id": stream_id,
                    "camera_ip": camera_ip,
                    "rtsp_url": rtsp_url,
                    "feed_url": f"/api/video_feed/{stream_id}"
                })

                logger.info(f"Started stream {stream_id} for camera {camera_ip}")

            except Exception as e:
                error_msg = f"Failed to start stream for camera {camera_ip}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        response = {
            "collection": collection_name,
            "started_streams": started_streams,
            "count": len(started_streams)
        }

        if errors:
            response["errors"] = errors

        return JSONResponse(response)

    except Exception as e:
        logger.error(f"Error starting collection streams: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Legacy endpoints for compatibility with existing frontend
@app.get("/restart-stream/{collection_name}/{camera_ip}")
async def restart_stream(collection_name: str, camera_ip: str):
    """Restart a specific camera stream using new MJPEG system"""
    try:
        logger.debug(f"Restarting stream for camera {camera_ip} in collection {collection_name}")

        if not os.path.exists(CAMERA_JSON_PATH):
            logger.error(f"Config file not found at: {CAMERA_JSON_PATH}")
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        if collection_name not in camera_data:
            logger.error(f"Collection '{collection_name}' not found in camera data")
            return {"error": "Collection not found"}

        if camera_ip not in camera_data[collection_name]:
            logger.error(f"Camera IP '{camera_ip}' not found in collection '{collection_name}'")
            return {"error": "Camera IP not found in collection"}

        # Get the RTSP URL for this camera
        rtsp_url = camera_data[collection_name][camera_ip]
        stream_id = f"{collection_name}_{camera_ip}"

        # Stop existing stream if it exists
        if stream_id in active_streams:
            active_streams[stream_id].stop()
            del active_streams[stream_id]

        # Create and start new stream
        stream = RTSPStream(rtsp_url)
        stream.start()
        active_streams[stream_id] = stream

        logger.info(f"Restarted stream {stream_id} for camera {camera_ip}")

        return {
            "status": "success",
            "stream_url": f"/api/video_feed/{stream_id}",
            "stream_id": stream_id
        }

    except Exception as e:
        logger.error(f"Error restarting stream: {str(e)}")
        return {"error": str(e)}

@app.get("/start-streams/{collection_name}")
async def start_camera_streams(collection_name: str):
    """Start MJPEG streams for all cameras in a collection (legacy endpoint)"""
    try:
        logger.debug(f"Starting streams for collection: {collection_name}")
        logger.debug(f"Looking for config file at: {CAMERA_JSON_PATH}")

        if not os.path.exists(CAMERA_JSON_PATH):
            logger.error(f"Config file not found at: {CAMERA_JSON_PATH}")
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)
            logger.debug(f"Loaded camera data: {json.dumps(camera_data, indent=2)}")
            logger.debug(f"Available collections: {list(camera_data.keys())}")

        if collection_name not in camera_data:
            logger.error(f"Collection '{collection_name}' not found in camera data")
            return {"error": "Collection not found"}

        # Start MJPEG streams
        stream_urls = []
        errors = []

        for camera_ip, rtsp_url in camera_data[collection_name].items():
            stream_id = f"{collection_name}_{camera_ip}"
            logger.debug(f"Starting stream for {stream_id} with URL: {rtsp_url}")

            try:
                # Stop existing stream if it exists
                if stream_id in active_streams:
                    active_streams[stream_id].stop()
                    del active_streams[stream_id]

                # Create and start new stream
                stream = RTSPStream(rtsp_url)
                stream.start()
                active_streams[stream_id] = stream

                # Store the stream URL in our list
                stream_urls.append(f"/api/video_feed/{stream_id}")

            except Exception as e:
                error_msg = f"Camera {camera_ip}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        response = {
            "collection": collection_name,
            "streams": stream_urls,
            "count": len(stream_urls)
        }

        if errors:
            response["warnings"] = errors

        return response
    except Exception as e:
        logger.error(f"Error starting streams: {str(e)}")
        return {"error": str(e)}

@app.get("/collections")
async def get_collections():
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        collections = list(camera_data.keys())
        return {"collections": collections}
    except Exception as e:
        return {"error": str(e)}

@app.get("/webrtc-streams/{collection_name}")
async def get_webrtc_streams(collection_name: str):
    """Get WebRTC stream information for all cameras in a collection"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return JSONResponse({"error": "camera_configuration.json not found"}, status_code=404)

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        if collection_name not in camera_data:
            return JSONResponse({"error": "Collection not found"}, status_code=404)

        # Create stream info for each camera in the collection
        streams = []
        for camera_ip, rtsp_url in camera_data[collection_name].items():
            stream_info = {
                "stream_id": f"webrtc_{collection_name}_{camera_ip}",
                "room_id": f"{collection_name}_{camera_ip}",
                "camera_ip": camera_ip,
                "rtsp_url": rtsp_url,
                "collection_name": collection_name
            }
            streams.append(stream_info)

        return JSONResponse({
            "success": True,
            "streams": streams,
            "collection": collection_name,
            "count": len(streams)
        })

    except Exception as e:
        logger.error(f"Error getting WebRTC streams for collection {collection_name}: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/cameras")
async def get_cameras():
    """Get all cameras from the configuration file"""
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            return {"error": "camera_configuration.json not found"}

        with open(CAMERA_JSON_PATH, "r") as f:
            camera_data = json.load(f)

        return {"cameras": camera_data}
    except Exception as e:
        logger.error(f"Error getting cameras: {str(e)}")
        return {"error": str(e)}

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    basic_health = {
        "status": "healthy",
        "active_streams": len(active_streams),
        "stream_ids": list(active_streams.keys())
    }

    if monitor_available:
        basic_health["monitoring"] = stream_monitor.get_summary_stats()

    return basic_health

# Stream health monitoring endpoints
@app.get("/api/stream_health/{stream_id}")
async def get_stream_health(stream_id: str):
    """Get detailed health information for a specific stream"""
    if not monitor_available:
        return JSONResponse({"error": "Stream monitoring not available"}, status_code=503)

    health_data = get_stream_diagnostics(stream_id)
    if "error" in health_data:
        return JSONResponse(health_data, status_code=404)

    return JSONResponse(health_data)

@app.get("/api/stream_health")
async def get_all_streams_health():
    """Get health information for all streams"""
    if not monitor_available:
        return JSONResponse({"error": "Stream monitoring not available"}, status_code=503)

    return JSONResponse({
        "streams": stream_monitor.get_all_streams_health(),
        "summary": stream_monitor.get_summary_stats()
    })

@app.get("/api/stream_diagnostics/{stream_id}")
async def get_detailed_stream_diagnostics(stream_id: str):
    """Get comprehensive diagnostics and recommendations for a stream"""
    if not monitor_available:
        return JSONResponse({"error": "Stream monitoring not available"}, status_code=503)

    diagnostics = get_stream_diagnostics(stream_id)
    if "error" in diagnostics:
        return JSONResponse(diagnostics, status_code=404)

    # Add current stream status from active_streams
    if stream_id in active_streams:
        stream = active_streams[stream_id]
        diagnostics["current_stream_info"] = {
            "is_running": stream.is_running,
            "rtsp_url": stream.rtsp_url,
            "has_capture": stream.cap is not None and stream.cap.isOpened() if stream.cap else False
        }

    return JSONResponse(diagnostics)

# Include the routers
app.include_router(analytics.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(camera_rules.router)
app.include_router(collections.router)
app.include_router(augment.router)
app.include_router(webrtc.router)
app.include_router(archive.router)
app.include_router(camera_settings.router)
app.include_router(dashboard_analytics.router)
app.include_router(appearance_search.router)
# Vehicle monitoring routes
try:
    from routes import vehicle_monitoring
    app.include_router(vehicle_monitoring.router)

    @app.on_event("startup")
    async def _start_vehicle_monitors():
        try:
            await vehicle_monitoring.start_all_vehicle_monitors_on_startup()
        except Exception as e:
            logger.error(f"Vehicle monitoring startup failed: {e}")
except Exception as e:
    logger.warning(f"Vehicle monitoring routes not available: {e}")


# Setup Socket.IO for WebRTC signaling
webrtc_signaling.setup_socketio(app, '/socket.io')

@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """
    Delete a collection from camera_configuration.json.
    - Backs up the old file to camera_configuration.json.bak
    - Returns 200 OK on success, 404 if not found, 500 on error
    """
    try:
        if not os.path.exists(CAMERA_JSON_PATH):
            logger.error(f"Config file not found at: {CAMERA_JSON_PATH}")
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": "camera_configuration.json not found"})

        # Read current config
        with open(CAMERA_JSON_PATH, "r") as f:
            try:
                camera_data = json.load(f)
            except Exception as e:
                logger.error(f"Error parsing camera_configuration.json: {e}")
                return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Malformed camera_configuration.json"})

        if collection_name not in camera_data:
            logger.warning(f"Collection '{collection_name}' not found in configuration")
            return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"error": f"Collection '{collection_name}' not found in configuration"})

        # Remove the collection
        del camera_data[collection_name]

        # Backup the old file
        backup_path = CAMERA_JSON_PATH + ".bak"
        try:
            shutil.copy2(CAMERA_JSON_PATH, backup_path)
        except Exception as e:
            logger.error(f"Failed to backup camera_configuration.json: {e}")
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Failed to backup configuration file"})

        # Write to a temp file first
        temp_path = CAMERA_JSON_PATH + ".tmp"
        try:
            with open(temp_path, "w") as f:
                json.dump(camera_data, f, indent=2)
            os.replace(temp_path, CAMERA_JSON_PATH)
        except Exception as e:
            logger.error(f"Failed to write updated configuration: {e}")
            return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": "Failed to write updated configuration"})

        logger.info(f"Collection '{collection_name}' deleted successfully.")
        return {"message": f"Collection '{collection_name}' deleted successfully."}
    except Exception as e:
        logger.error(f"Unexpected error deleting collection: {e}")
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"error": str(e)})

if __name__ == "__main__":
    # Configure uvicorn to disable access logging to reduce noise
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        access_log=False,  # Disable access logging to prevent unwanted HTTP request logs
        log_level="info"   # Keep application logs at info level
    )