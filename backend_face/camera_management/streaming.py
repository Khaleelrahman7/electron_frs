import cv2
import threading
import time
import logging
from typing import Dict, Optional
import uuid
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import io
import numpy as np

logger = logging.getLogger(__name__)

class CameraStreamManager:
    """Manages camera streams for the enhanced camera management system"""
    
    def __init__(self):
        self.active_streams: Dict[str, Dict] = {}
        self.stream_lock = threading.Lock()
    
    def start_stream(self, camera_id: int, rtsp_url: str) -> str:
        """Start a new camera stream"""
        stream_id = str(uuid.uuid4())
        
        try:
            # Test the RTSP connection (handle camera index vs RTSP URL)
            if isinstance(rtsp_url, str) and rtsp_url.isdigit():
                cap = cv2.VideoCapture(int(rtsp_url))
            else:
                cap = cv2.VideoCapture(rtsp_url)
            
            if not cap.isOpened():
                raise HTTPException(status_code=400, detail="Cannot connect to camera stream")
            
            # Read a test frame
            ret, frame = cap.read()
            if not ret:
                cap.release()
                raise HTTPException(status_code=400, detail="Cannot read from camera stream")
            
            cap.release()
            
            # Store stream info
            with self.stream_lock:
                self.active_streams[stream_id] = {
                    'camera_id': camera_id,
                    'rtsp_url': rtsp_url,
                    'created_at': time.time(),
                    'is_active': True,
                    'frame_count': 0
                }
            
            logger.info(f"Started stream {stream_id} for camera {camera_id}")
            return stream_id
            
        except Exception as e:
            logger.error(f"Error starting stream for camera {camera_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to start stream: {str(e)}")
    
    def stop_stream(self, stream_id: str) -> bool:
        """Stop a camera stream"""
        try:
            with self.stream_lock:
                if stream_id in self.active_streams:
                    self.active_streams[stream_id]['is_active'] = False
                    del self.active_streams[stream_id]
                    logger.info(f"Stopped stream {stream_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error stopping stream {stream_id}: {e}")
            return False
    
    def get_stream_info(self, stream_id: str) -> Optional[Dict]:
        """Get information about a stream"""
        with self.stream_lock:
            return self.active_streams.get(stream_id)
    
    def _is_stream_active(self, stream_id: str) -> bool:
        """Check if a stream is still active (exists and is_active=True)"""
        with self.stream_lock:
            stream = self.active_streams.get(stream_id)
            return stream is not None and stream.get('is_active', False)
    
    def get_camera_stream(self, camera_id: int) -> Optional[str]:
        """Get active stream ID for a camera"""
        with self.stream_lock:
            for stream_id, info in self.active_streams.items():
                if info['camera_id'] == camera_id and info['is_active']:
                    return stream_id
        return None
    
    def generate_mjpeg_stream(self, stream_id: str):
        """Generate MJPEG stream for a camera with improved stability"""
        stream_info = self.get_stream_info(stream_id)
        if not stream_info:
            return

        rtsp_url = stream_info['rtsp_url']
        logger.info(f"Starting MJPEG stream generation for {stream_id}")

        # Try to connect to real camera first
        cap = None
        camera_accessible = False

        try:
            # Handle camera index (0, 1, 2, etc.) vs RTSP URL
            if isinstance(rtsp_url, str) and rtsp_url.isdigit():
                cap = cv2.VideoCapture(int(rtsp_url))
            else:
                cap = cv2.VideoCapture(rtsp_url)
                
            if cap.isOpened():
                # Test with multiple frames to ensure stable connection
                test_frames_count = 0
                for _ in range(3):
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None and test_frame.size > 0:
                        test_frames_count += 1
                    time.sleep(0.1)

                if test_frames_count >= 2:  # At least 2 successful frames
                    camera_accessible = True
                    logger.info(f"Camera accessible for stream {stream_id} ({test_frames_count}/3 test frames)")
                else:
                    logger.warning(f"Camera unstable for stream {stream_id} ({test_frames_count}/3 test frames)")

            if cap:
                cap.release()
                cap = None
        except Exception as e:
            logger.warning(f"Error testing camera for stream {stream_id}: {e}")
            if cap:
                cap.release()
                cap = None

        # If camera is not accessible, generate demo stream
        if not camera_accessible:
            logger.warning(f"Camera not accessible for stream {stream_id}, generating demo stream")
            yield from self._generate_demo_stream(stream_id, stream_info)
            return

        # Real camera streaming with improved stability
        yield from self._generate_real_camera_stream(stream_id, stream_info, rtsp_url)

    def _generate_real_camera_stream(self, stream_id: str, stream_info: Dict, rtsp_url: str):
        """Generate stream from real camera with enhanced stability"""
        cap = None
        consecutive_failures = 0
        max_failures = 10
        frame_count = 0
        last_frame = None
        reconnect_attempts = 0
        max_reconnect_attempts = 5

        # JPEG encoding parameters for better performance
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]

        while self._is_stream_active(stream_id) and reconnect_attempts < max_reconnect_attempts:
            try:
                # Connect to camera
                if cap is None or not cap.isOpened():
                    logger.info(f"Connecting to camera for stream {stream_id}")
                    # Handle camera index (0, 1, 2, etc.) vs RTSP URL
                    if isinstance(rtsp_url, str) and rtsp_url.isdigit():
                        cap = cv2.VideoCapture(int(rtsp_url))
                    else:
                        cap = cv2.VideoCapture(rtsp_url)

                    if cap.isOpened():
                        # Optimize capture settings
                        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffering
                        cap.set(cv2.CAP_PROP_FPS, 25)  # Target 25 FPS

                        # Set timeouts
                        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 30000)  # 30 seconds
                        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)   # 5 seconds

                        logger.info(f"Successfully connected to camera for stream {stream_id}")
                        consecutive_failures = 0
                    else:
                        raise Exception("Failed to open camera")

                # Read frame
                ret, frame = cap.read()

                if ret and frame is not None and frame.size > 0:
                    consecutive_failures = 0
                    last_frame = frame.copy()

                    # Apply face detection and recognition
                    processed_frame = frame
                    try:
                        # Try to import and use face pipeline for processing
                        from face_pipeline import process_frame as face_process_frame
                        processed_frame, _ = face_process_frame(frame)
                    except Exception as face_error:
                        # If face processing fails, use raw frame
                        logger.debug(f"Face processing skipped for stream {stream_id}: {face_error}")
                        processed_frame = frame

                    # Encode frame
                    try:
                        ret_encode, buffer = cv2.imencode('.jpg', processed_frame, encode_params)
                        if ret_encode and buffer is not None:
                            # Update stream info
                            with self.stream_lock:
                                if stream_id in self.active_streams:
                                    self.active_streams[stream_id]['frame_count'] = frame_count
                                    self.active_streams[stream_id]['last_frame_time'] = time.time()

                            # Yield frame
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n'
                                   b'Content-Length: ' + str(len(buffer)).encode() + b'\r\n\r\n' +
                                   buffer.tobytes() + b'\r\n')

                            frame_count += 1
                        else:
                            logger.warning(f"Failed to encode frame for stream {stream_id}")
                    except Exception as encode_error:
                        logger.error(f"Frame encoding error for stream {stream_id}: {encode_error}")
                else:
                    consecutive_failures += 1
                    logger.warning(f"Failed to read frame {consecutive_failures}/{max_failures} for stream {stream_id}")

                    if consecutive_failures >= max_failures:
                        logger.error(f"Too many consecutive failures for stream {stream_id}, reconnecting...")
                        if cap:
                            cap.release()
                            cap = None
                        reconnect_attempts += 1
                        time.sleep(2)  # Wait before reconnecting
                        continue

                    # Use last frame if available
                    if last_frame is not None:
                        try:
                            ret_encode, buffer = cv2.imencode('.jpg', last_frame, encode_params)
                            if ret_encode and buffer is not None:
                                yield (b'--frame\r\n'
                                       b'Content-Type: image/jpeg\r\n'
                                       b'Content-Length: ' + str(len(buffer)).encode() + b'\r\n\r\n' +
                                       buffer.tobytes() + b'\r\n')
                        except:
                            pass

                # Control frame rate
                time.sleep(0.04)  # ~25 FPS

            except Exception as e:
                logger.error(f"Error in camera stream {stream_id}: {e}")
                if cap:
                    cap.release()
                    cap = None
                reconnect_attempts += 1
                time.sleep(2)

        # Cleanup
        if cap:
            cap.release()

        # If we exhausted reconnection attempts, fall back to demo
        if reconnect_attempts >= max_reconnect_attempts:
            logger.warning(f"Max reconnection attempts reached for stream {stream_id}, falling back to demo")
            yield from self._generate_demo_stream(stream_id, stream_info)

    def _generate_demo_stream(self, stream_id: str, stream_info: Dict):
        """Generate a demo stream when real camera is not available"""
        import numpy as np
        import datetime

        frame_count = 0
        start_time = time.time()

        try:
            while self._is_stream_active(stream_id):
                # Create a demo frame (640x480)
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
                camera_id = stream_info.get('camera_id', 'Unknown')
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Add text overlays
                cv2.putText(frame, f"DEMO CAMERA {camera_id}", (50, 50),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(frame, f"Time: {current_time}", (50, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"Frame: {frame_count}", (50, 130),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"FPS: 30", (50, 160),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, "Camera Offline - Demo Mode", (50, 400),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

                # Add moving elements
                elapsed = time.time() - start_time
                circle_x = int(320 + 200 * np.sin(elapsed))
                circle_y = int(240 + 100 * np.cos(elapsed * 1.5))
                cv2.circle(frame, (circle_x, circle_y), 20, (0, 255, 255), -1)

                # Add timestamp in corner
                cv2.putText(frame, f"Uptime: {int(elapsed)}s", (450, 450),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

                # Encode frame as JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if not ret:
                    continue

                # Update frame count
                with self.stream_lock:
                    if stream_id in self.active_streams:
                        self.active_streams[stream_id]['frame_count'] += 1

                # Yield frame in MJPEG format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

                frame_count += 1
                time.sleep(0.033)  # ~30 FPS

        except Exception as e:
            logger.error(f"Error in demo stream {stream_id}: {e}")
        finally:
            self.stop_stream(stream_id)

    def get_active_streams(self) -> Dict[str, Dict]:
        """Get all active streams"""
        with self.stream_lock:
            return self.active_streams.copy()
    
    def cleanup_inactive_streams(self):
        """Clean up streams that have been inactive for too long"""
        current_time = time.time()
        inactive_threshold = 300  # 5 minutes
        
        with self.stream_lock:
            inactive_streams = []
            for stream_id, info in self.active_streams.items():
                if current_time - info['created_at'] > inactive_threshold and not info['is_active']:
                    inactive_streams.append(stream_id)
            
            for stream_id in inactive_streams:
                del self.active_streams[stream_id]
                logger.info(f"Cleaned up inactive stream {stream_id}")

# Global stream manager instance
stream_manager = CameraStreamManager()

def get_stream_manager() -> CameraStreamManager:
    """Get the global stream manager instance"""
    return stream_manager
