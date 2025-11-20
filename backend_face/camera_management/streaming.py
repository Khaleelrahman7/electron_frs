import cv2
import threading
import time
import logging
from typing import Dict, Optional, Tuple, List
import uuid
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import io
import numpy as np
from queue import Queue, Empty
from collections import deque
import os
import platform

logger = logging.getLogger(__name__)

class CameraStreamManager:
    """Manages camera streams for the enhanced camera management system"""
    
    def __init__(self):
        self.active_streams: Dict[str, Dict] = {}
        self.stream_lock = threading.Lock()
        # Per-stream frame processing queues and threads
        self.processing_queues: Dict[str, Queue] = {}
        self.processed_frames: Dict[str, deque] = {}  # Buffer of processed frames
        self.processing_threads: Dict[str, threading.Thread] = {}
        self.frame_counters: Dict[str, int] = {}  # Per-stream frame counters
        self.max_buffer_size = 3  # Keep max 3 processed frames in buffer
        # Frame quality tracking
        self.last_good_frames: Dict[str, np.ndarray] = {}  # Store last valid frame per stream
        self.frame_validation_enabled = True
        # Frame buffer for sharp face capture (stores raw frames with timestamps)
        self.frame_buffers: Dict[str, deque] = {}  # Buffer of raw frames for best capture
        self.max_frame_buffer_size = 20  # Optimized for Tesla T4: More frames = better sharpness selection
        
        # Set FFmpeg environment variables to suppress H.264 error messages and handle errors better
        os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|strict;experimental|err_detect;ignore_err'
        # Suppress FFmpeg stderr output for H.264 errors (they're handled gracefully)
        os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'
    
    def _open_camera_capture(self, rtsp_url: str, retry_backends: bool = True):
        """Open camera capture with appropriate backend, trying multiple backends if needed"""
        is_camera_index = isinstance(rtsp_url, str) and rtsp_url.isdigit()
        camera_index = int(rtsp_url) if is_camera_index else None
        
        # For camera indices on Windows, prefer DirectShow over MSMF
        if is_camera_index and platform.system() == 'Windows':
            backends_to_try = [
                (cv2.CAP_DSHOW, "DirectShow"),
                (cv2.CAP_ANY, "Default"),
            ]
        elif is_camera_index:
            # Linux/Mac - try default first
            backends_to_try = [
                (cv2.CAP_ANY, "Default"),
                (cv2.CAP_V4L2, "V4L2"),  # Linux
            ]
        else:
            # RTSP URL - use FFMPEG
            backends_to_try = [
                (cv2.CAP_FFMPEG, "FFMPEG"),
            ]
        
        last_error = None
        for backend, backend_name in backends_to_try:
            try:
                if is_camera_index:
                    cap = cv2.VideoCapture(camera_index, backend)
                else:
                    cap = cv2.VideoCapture(rtsp_url, backend)
                
                if cap.isOpened():
                    # Try to read a test frame to verify it works
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        logger.info(f"Successfully opened camera with {backend_name} backend")
                        return cap
                    else:
                        cap.release()
                        logger.warning(f"Camera opened with {backend_name} but cannot read frames")
                else:
                    if cap:
                        cap.release()
            except Exception as e:
                last_error = e
                logger.debug(f"Failed to open camera with {backend_name}: {e}")
                continue
        
        # If all backends failed, raise informative error
        error_msg = f"Cannot connect to camera"
        if is_camera_index:
            error_msg += f" (index {camera_index})"
            error_msg += ". Camera may be in use by another application, disconnected, or index may be incorrect."
        else:
            error_msg += f" (URL: {rtsp_url})"
        
        if last_error:
            error_msg += f" Last error: {str(last_error)}"
        
        raise Exception(error_msg)
    
    def start_stream(self, camera_id: int, rtsp_url: str) -> str:
        """Start a new camera stream"""
        stream_id = str(uuid.uuid4())
        
        try:
            # Test the camera connection with appropriate backend
            cap = self._open_camera_capture(rtsp_url)
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
            
        except HTTPException:
            raise
        except Exception as e:
            error_detail = str(e) if str(e) else "Unknown error occurred"
            logger.error(f"Error starting stream for camera {camera_id}: {error_detail}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to start stream: {error_detail}")
    
    def stop_stream(self, stream_id: str) -> bool:
        """Stop a camera stream"""
        try:
            # Stop processing thread
            if stream_id in self.processing_threads:
                if stream_id in self.processing_queues:
                    # Signal stop by putting None
                    try:
                        self.processing_queues[stream_id].put(None, timeout=0.1)
                    except:
                        pass
                # Wait for thread to finish (with timeout)
                thread = self.processing_threads[stream_id]
                if thread.is_alive():
                    thread.join(timeout=2.0)
                del self.processing_threads[stream_id]
            
            # Clean up queues and buffers
            if stream_id in self.processing_queues:
                del self.processing_queues[stream_id]
            if stream_id in self.processed_frames:
                del self.processed_frames[stream_id]
            if stream_id in self.frame_counters:
                del self.frame_counters[stream_id]
            if stream_id in self.last_good_frames:
                del self.last_good_frames[stream_id]
            if stream_id in self.frame_buffers:
                del self.frame_buffers[stream_id]
            
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
    
    def _validate_frame(self, frame: np.ndarray) -> bool:
        """Validate frame quality - check for corruption or pixelation"""
        if frame is None:
            return False
        if frame.size == 0:
            return False
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            return False
        
        h, w = frame.shape[:2]
        if h < 10 or w < 10:  # Too small
            return False
        
        # Check for completely black or white frames (likely corruption)
        mean_val = np.mean(frame)
        if mean_val < 5 or mean_val > 250:
            return False
        
        # Check for excessive noise or pixelation patterns
        # Sample a few regions to check for blocky artifacts
        sample_regions = [
            frame[0:h//4, 0:w//4],      # Top-left
            frame[h//4:h//2, w//2:3*w//4],  # Center
            frame[3*h//4:h, 3*w//4:w]    # Bottom-right
        ]
        
        for region in sample_regions:
            if region.size > 0:
                region_std = np.std(region)
                # Very low std might indicate blocky/pixelated regions
                if region_std < 0.5:
                    return False
        
        return True
    
    def generate_mjpeg_stream(self, stream_id: str):
        """Generate MJPEG stream for a camera with improved stability"""
        stream_info = self.get_stream_info(stream_id)
        if not stream_info:
            return

        rtsp_url = stream_info['rtsp_url']
        logger.info(f"Starting MJPEG stream generation for {stream_id}")

        # Try to connect to real camera first and reuse the connection
        cap = None
        camera_accessible = False

        try:
            # Use helper method to open camera with appropriate backend
            cap = self._open_camera_capture(rtsp_url, retry_backends=False)
                
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

        except Exception as e:
            logger.warning(f"Error testing camera for stream {stream_id}: {e}")
            if cap:
                cap.release()
                cap = None

        # Always try to stream from real camera, even if initial test failed
        # This allows for cameras that take time to initialize
        if not camera_accessible:
            logger.warning(f"Camera initial test failed for stream {stream_id}, but will attempt real stream anyway")
            # If test failed, release the cap and let _generate_real_camera_stream open a new one
            if cap:
                cap.release()
                cap = None

        # Real camera streaming with improved stability - reuse the connection if available
        yield from self._generate_real_camera_stream(stream_id, stream_info, rtsp_url, pre_opened_cap=cap)

    def _focus_measure(self, gray: np.ndarray) -> float:
        """Calculate sharpness using variance of Laplacian (improved for better detection)"""
        try:
            # Use Laplacian variance for sharpness
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Also check gradient magnitude for additional sharpness metric
            grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient_mag = np.sqrt(grad_x**2 + grad_y**2).mean()
            
            # Combine both metrics (weighted average)
            combined_score = laplacian_var * 0.7 + gradient_mag * 0.3
            return combined_score
        except:
            return 0.0
    
    def _get_best_frame_from_buffer(self, stream_id: str, bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """Get the sharpest frame from buffer for the given bounding box"""
        buffer = self.frame_buffers.get(stream_id)
        if not buffer or len(buffer) == 0:
            return None
        
        x1, y1, x2, y2 = bbox
        best_frame = None
        best_score = -1
        
        for frame_data in buffer:
            frame, _ = frame_data
            if frame is None:
                continue
            
            h, w = frame.shape[:2]
            # Clamp bbox to frame bounds
            x1_c = max(0, min(w-1, x1))
            y1_c = max(0, min(h-1, y1))
            x2_c = max(0, min(w-1, x2))
            y2_c = max(0, min(h-1, y2))
            
            if x2_c <= x1_c or y2_c <= y1_c:
                continue
            
            # Extract crop
            crop = frame[y1_c:y2_c, x1_c:x2_c]
            if crop.size == 0:
                continue
            
            # Convert to grayscale and measure sharpness
            if len(crop.shape) == 3:
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            else:
                gray = crop
            
            score = self._focus_measure(gray)
            if score > best_score:
                best_score = score
                best_frame = frame.copy()
        
        # Only return if sharpness is above threshold (avoid very blurry faces)
        # Lowered threshold slightly but improved measurement should catch more good frames
        if best_score < 30:  # Threshold for acceptable sharpness (reduced from 50, improved measurement compensates)
            return None
        
        return best_frame
    
    def _face_processing_worker(self, stream_id: str):
        """Background worker thread for async face processing"""
        queue = self.processing_queues.get(stream_id)
        if not queue:
            return
        
        try:
            while self._is_stream_active(stream_id):
                try:
                    # Get frame from queue (with timeout to allow checking stream status)
                    frame_data = queue.get(timeout=0.5)

                    # None signals stop
                    if frame_data is None:
                        break

                    frame, frame_num = frame_data

                    # Process every frame continuously for face detection and capture
                    try:
                        from face_pipeline import process_frame as face_process_frame
                        # Get frame with detections drawn (face_pipeline draws them)
                        processed_frame, _ = face_process_frame(frame, force_process=True, stream_id=stream_id)
                    except Exception as face_error:
                        logger.debug(f"Face processing error for stream {stream_id}: {face_error}")
                        processed_frame = frame.copy()
                    
                    # Add to processed frames buffer (thread-safe)
                    if stream_id not in self.processed_frames:
                        self.processed_frames[stream_id] = deque(maxlen=self.max_buffer_size)
                    
                    buffer = self.processed_frames[stream_id]
                    buffer.append((processed_frame, frame_num, time.time()))
                    
                    queue.task_done()
                    
                except Empty:
                    continue
                except Exception as e:
                    logger.error(f"Error in face processing worker for {stream_id}: {e}")
                    continue
        except Exception as e:
            logger.error(f"Face processing worker exited for {stream_id}: {e}")
    
    def _generate_real_camera_stream(self, stream_id: str, stream_info: Dict, rtsp_url: str, pre_opened_cap=None):
        """Generate stream from real camera with enhanced stability and async face processing"""
        cap = pre_opened_cap  # Use pre-opened capture if provided
        is_reusing_connection = pre_opened_cap is not None and pre_opened_cap.isOpened()
        connection_logged = is_reusing_connection
        consecutive_failures = 0
        max_failures = 10
        frame_count = 0
        last_frame = None
        reconnect_attempts = 0
        max_reconnect_attempts = 5

        # JPEG encoding parameters - Optimized for Tesla T4: High quality for clear streams
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, 95]
        
        # Initialize processing queue and thread for this stream
        if stream_id not in self.processing_queues:
            self.processing_queues[stream_id] = Queue(maxsize=2)  # Small queue to prevent lag
            self.processed_frames[stream_id] = deque(maxlen=self.max_buffer_size)
            self.frame_counters[stream_id] = 0
            
            # Start processing thread
            processing_thread = threading.Thread(
                target=self._face_processing_worker,
                args=(stream_id,),
                daemon=True
            )
            processing_thread.start()
            self.processing_threads[stream_id] = processing_thread
            logger.info(f"Started face processing thread for stream {stream_id}")

        # Keep retrying as long as stream is active - no demo fallback
        while self._is_stream_active(stream_id):
            try:
                # Connect to camera (only if not already connected)
                if cap is None or not cap.isOpened():
                    connection_logged = False
                    if pre_opened_cap is not None and pre_opened_cap.isOpened():
                        # Reuse pre-opened connection
                        cap = pre_opened_cap
                        logger.info(f"Reusing existing camera connection for stream {stream_id}")
                    else:
                        logger.info(f"Connecting to camera for stream {stream_id}")
                        # Use helper method to open camera with appropriate backend
                        try:
                            cap = self._open_camera_capture(rtsp_url, retry_backends=True)
                        except Exception as open_error:
                            logger.error(f"Failed to open camera for stream {stream_id}: {open_error}")
                            consecutive_failures += 1
                            if consecutive_failures >= max_failures:
                                reconnect_attempts += 1
                                if reconnect_attempts >= max_reconnect_attempts:
                                    logger.error(f"Max reconnection attempts reached for stream {stream_id}")
                                    break
                                time.sleep(2)
                            continue

                if cap.isOpened():
                    # Optimize capture settings to reduce H.264 errors
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffering to reduce latency
                    cap.set(cv2.CAP_PROP_FPS, 25)  # Target 25 FPS
                    
                    # Enhanced GPU acceleration for Tesla T4 (NVDEC hardware decoding)
                    if not isinstance(rtsp_url, str) or not rtsp_url.isdigit():
                        try:
                            # Optimized for Tesla T4: Full GPU acceleration for video decoding
                            # This uses NVDEC on NVIDIA GPUs for hardware-accelerated decoding
                            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = (
                                'rtsp_transport;tcp|'
                                'fflags;nobuffer|'
                                'flags;low_delay|'
                                'strict;experimental|'
                                'err_detect;ignore_err|'
                                'hwaccel;nvdec|'  # NVIDIA hardware acceleration
                                'hwaccel_device;0|'
                                'hwaccel_output_format;cuda|'  # Keep frames on GPU when possible
                                'c:v;h264_cuvid'  # Explicit CUDA decoder for H.264
                            )
                            logger.info(f"Enabled NVDEC GPU acceleration for stream {stream_id}")
                        except Exception as gpu_err:
                            logger.warning(f"GPU acceleration setup failed for stream {stream_id}: {gpu_err}")
                            pass
                        
                        try:
                            # Try to set MJPG codec preference (less errors than H264)
                            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
                        except:
                            pass  # Some cameras don't support codec change
                    
                    # Set timeouts
                    try:
                        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 30000)  # 30 seconds
                        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)   # 5 seconds
                    except:
                        pass  # Some backends don't support timeouts

                    if not connection_logged:
                        logger.info(f"Successfully connected to camera for stream {stream_id}")
                        connection_logged = True
                    consecutive_failures = 0
                    # Clear pre_opened_cap after first use to prevent reuse on reconnection
                    pre_opened_cap = None
                    is_reusing_connection = False
                else:
                    raise Exception("Failed to open camera")

                # Use grab()/retrieve() pattern to avoid FFmpeg backlogs
                if not cap.grab():
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        logger.error(f"Too many consecutive grab failures for stream {stream_id}, reconnecting...")
                        if cap:
                            cap.release()
                            cap = None
                        reconnect_attempts += 1
                        time.sleep(2)
                        continue
                    time.sleep(0.01)
                    continue
                
                ret, frame = cap.retrieve()
                
                if ret and frame is not None and frame.size > 0:
                    # Validate frame quality - skip corrupted/pixelated frames
                    frame_valid = True
                    if self.frame_validation_enabled:
                        frame_valid = self._validate_frame(frame)
                    
                    if frame_valid:
                        consecutive_failures = 0
                        last_frame = frame.copy()
                        self.last_good_frames[stream_id] = frame.copy()  # Store good frame
                        frame_count += 1
                        self.frame_counters[stream_id] = frame_count

                        # Add to frame buffer for sharp face capture (use original resolution)
                        if stream_id not in self.frame_buffers:
                            self.frame_buffers[stream_id] = deque(maxlen=self.max_frame_buffer_size)
                        # Store full resolution frame for better quality captures
                        self.frame_buffers[stream_id].append((frame.copy(), frame_count))

                        # Send frame to processing queue (non-blocking)
                        queue = self.processing_queues.get(stream_id)
                        if queue:
                            try:
                                # Don't block if queue is full - drop frame to maintain real-time
                                queue.put_nowait((frame.copy(), frame_count))
                            except:
                                # Queue full, skip this frame for processing
                                pass

                        # Try to get processed frame from buffer (non-blocking)
                        processed_frame = None
                        buffer = self.processed_frames.get(stream_id)
                        if buffer and len(buffer) > 0:
                            try:
                                # Get most recent processed frame
                                processed_frame, _, _ = buffer[-1]
                            except:
                                pass
                        
                        # Fallback to raw frame if no processed frame available
                        if processed_frame is None:
                            processed_frame = frame

                        # Encode and send frame immediately (don't wait for processing)
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
                                
                                last_processed_frame = processed_frame
                            else:
                                logger.warning(f"Failed to encode frame for stream {stream_id}")
                        except Exception as encode_error:
                            logger.error(f"Frame encoding error for stream {stream_id}: {encode_error}")
                    else:
                        # Frame is corrupted - use last good frame
                        if stream_id in self.last_good_frames:
                            frame = self.last_good_frames[stream_id].copy()
                            # Continue with the good frame (don't increment failure counter)
                            # Send frame to processing queue
                            queue = self.processing_queues.get(stream_id)
                            if queue:
                                try:
                                    queue.put_nowait((frame.copy(), frame_count))
                                except:
                                    pass
                            
                            # Get processed frame or use raw
                            processed_frame = None
                            buffer = self.processed_frames.get(stream_id)
                            if buffer and len(buffer) > 0:
                                try:
                                    processed_frame, _, _ = buffer[-1]
                                except:
                                    pass
                            
                            if processed_frame is None:
                                processed_frame = frame
                            
                            # Send the good frame
                            try:
                                ret_encode, buffer = cv2.imencode('.jpg', processed_frame, encode_params)
                                if ret_encode and buffer is not None:
                                    yield (b'--frame\r\n'
                                           b'Content-Type: image/jpeg\r\n'
                                           b'Content-Length: ' + str(len(buffer)).encode() + b'\r\n\r\n' +
                                           buffer.tobytes() + b'\r\n')
                                    last_processed_frame = processed_frame
                            except:
                                pass
                        else:
                            # No good frame available yet, skip this frame
                            consecutive_failures += 1
                else:
                    consecutive_failures += 1
                    logger.warning(f"Failed to read frame {consecutive_failures}/{max_failures} for stream {stream_id}")

                    if consecutive_failures >= max_failures:
                        logger.error(f"Too many consecutive failures for stream {stream_id}, reconnecting...")
                        if cap:
                            cap.release()
                            cap = None
                            connection_logged = False
                        consecutive_failures = 0  # Reset for next reconnection attempt
                        time.sleep(2)  # Wait before reconnecting
                        continue

                    # Use last processed frame if available, otherwise last good raw frame
                    frame_to_send = None
                    if last_processed_frame is not None:
                        frame_to_send = last_processed_frame
                    elif stream_id in self.last_good_frames:
                        frame_to_send = self.last_good_frames[stream_id]
                    elif last_frame is not None:
                        frame_to_send = last_frame
                    
                    if frame_to_send is not None:
                        try:
                            ret_encode, buffer = cv2.imencode('.jpg', frame_to_send, encode_params)
                            if ret_encode and buffer is not None:
                                yield (b'--frame\r\n'
                                       b'Content-Type: image/jpeg\r\n'
                                       b'Content-Length: ' + str(len(buffer)).encode() + b'\r\n\r\n' +
                                       buffer.tobytes() + b'\r\n')
                        except:
                            pass

                # Control frame rate - adaptive based on processing time
                time.sleep(0.033)  # ~30 FPS target (slightly faster to compensate for processing delays)

            except Exception as e:
                logger.error(f"Error in camera stream {stream_id}: {e}")
                if cap:
                    cap.release()
                    cap = None
                    connection_logged = False
                consecutive_failures += 1
                time.sleep(2)  # Wait before retrying

        # Cleanup
        if cap:
            cap.release()

        # Keep retrying instead of falling back to demo
        # If we reach here, it means stream was stopped or deactivated
        logger.info(f"Stream {stream_id} ended - stream was stopped or deactivated")

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
