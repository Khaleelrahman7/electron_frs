# face_pipeline.py
import cv2
import numpy as np
import face_recognition
from insightface.app import FaceAnalysis
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict
import threading
import os
import time
from save_face import save_face_image

TOLERANCE = 0.44 # Stricter matching (lower = more strict). Was 0.5, now more selective
# Rate limit for saving same face per label (seconds)
MIN_SAVE_INTERVAL = 5.0

# Frame skipping removed - process every frame for maximum face capture quality
# Tesla T4 GPU can handle full frame processing efficiently

# Initialize detector and known faces (singleton-like)
# Support for multiple GPUs: maintain separate face_app instances per GPU
face_apps: Dict[int, Any] = {}  # GPU ID -> FaceAnalysis instance
face_app = None  # Default/fallback instance
known_encodings: List[np.ndarray] = []
known_names: List[str] = []
available_gpus: List[int] = []  # List of available GPU IDs

# Person tracking across frames: stream_id -> track_id -> tracking_info
# tracking_info: {
#   'name': str,  # Persisted name (once recognized, never changes to Unknown)
#   'bbox': (x1, y1, x2, y2),  # Last known bbox
#   'last_seen': float,  # Timestamp of last detection
#   'frame_count': int,  # Frames since first seen
#   'encoding': np.ndarray  # Face encoding for matching
# }
person_tracking: Dict[str, Dict[int, Dict[str, Any]]] = defaultdict(dict)
track_id_counter: Dict[str, int] = defaultdict(int)  # Per-stream track ID counter
tracking_lock = threading.Lock()  # Thread-safe access to tracking data

# Tracking parameters
IOU_THRESHOLD = 0.3  # Minimum IoU to match detections to tracked persons
MAX_TRACK_AGE_FRAMES = 30  # Remove tracks not seen for this many frames
MAX_TRACK_AGE_SECONDS = 2.0  # Remove tracks not seen for this many seconds


def check_gpu_availability() -> List[int]:
    """Check available GPUs for InsightFace/ONNXRuntime. Returns list of GPU IDs."""
    available = []
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if 'CUDAExecutionProvider' in providers:
            # Check how many GPUs are available
            try:
                import subprocess
                result = subprocess.run(['nvidia-smi', '--list-gpus'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Count GPUs from nvidia-smi output
                    gpu_count = len([line for line in result.stdout.strip().split('\n') if line.strip()])
                    for gpu_id in range(gpu_count):
                        available.append(gpu_id)
                    print(f"[INFO] Detected {gpu_count} GPU(s) via nvidia-smi")
                else:
                    # Fallback: try GPU 0
                    available.append(0)
                    print(f"[INFO] ONNX providers available: {providers}, assuming GPU 0")
            except Exception:
                # Fallback: try GPU 0
                available.append(0)
                print(f"[INFO] ONNX providers available: {providers}, using GPU 0")
        else:
            print(f"[INFO] CUDA provider not available. Available providers: {providers}")
    except ImportError:
        print("[WARN] onnxruntime not available")
    except Exception as e:
        print(f"[WARN] Error checking GPU availability: {e}")
    return available


def init(data_dir: str, ctx: int = -1, det_size: Tuple[int, int] = (640, 640), use_dual_gpu: bool = True) -> None:
    """Initialize known faces and InsightFace detector with GPU detection.
    
    Args:
        data_dir: Directory containing known face images
        ctx: GPU context ID (-1 for CPU, 0+ for GPU). If -1 and use_dual_gpu=True, auto-detects GPUs
        det_size: Detection size for InsightFace
        use_dual_gpu: If True, automatically initialize all available GPUs (up to 2)
    """
    global face_app, face_apps, known_encodings, known_names, available_gpus

    # Reuse your function from fr1.py
    try:
        from fr1 import load_known_faces
    except Exception as e:
        raise ImportError("Cannot import load_known_faces from fr1.py") from e

    known_encodings, known_names = load_known_faces(data_dir)

    # Clear existing instances
    face_apps = {}
    face_app = None
    available_gpus = []

    # Auto-detect and initialize multiple GPUs if requested
    if use_dual_gpu and ctx == -1:
        detected_gpus = check_gpu_availability()
        if detected_gpus:
            print(f"[INFO] Detected {len(detected_gpus)} GPU(s): {detected_gpus}")
            # Initialize up to 2 GPUs for optimal performance
            for gpu_id in detected_gpus[:2]:
                try:
                    app = FaceAnalysis(allowed_modules=['detection'])
                    app.prepare(ctx_id=gpu_id, det_size=det_size)
                    face_apps[gpu_id] = app
                    available_gpus.append(gpu_id)
                    print(f"[face_pipeline] Initialized GPU {gpu_id} successfully, det_size={det_size}")
                except Exception as e:
                    print(f"[WARN] Failed to initialize GPU {gpu_id}: {e}")
            
            if face_apps:
                # Set default to first GPU
                face_app = face_apps[available_gpus[0]]
                print(f"[INFO] Using {len(face_apps)} GPU(s) for face detection")
            else:
                print("[WARN] All GPU initializations failed, falling back to CPU")
                ctx = -1
        else:
            print("[INFO] No GPUs detected, using CPU")
            ctx = -1

    # Initialize single GPU or CPU if dual GPU not used or failed
    if not face_apps:
        if ctx == 0:
            detected_gpus = check_gpu_availability()
            if detected_gpus:
                ctx = detected_gpus[0]
                print(f"[INFO] Using GPU {ctx} for face detection")
            else:
                print("[WARN] GPU requested but not available, using CPU")
                ctx = -1
        elif ctx == -1:
            print("[INFO] Using CPU for face detection")

        try:
            face_app = FaceAnalysis(allowed_modules=['detection'])
            face_app.prepare(ctx_id=ctx, det_size=det_size)
            if ctx >= 0:
                face_apps[ctx] = face_app
                available_gpus.append(ctx)
            print(f"[face_pipeline] Initialized successfully with ctx={ctx}, det_size={det_size}")
        except Exception as e:
            # If GPU init fails, try CPU
            if ctx != -1:
                print(f"[WARN] GPU initialization failed: {e}")
                print("[INFO] Falling back to CPU")
                try:
                    face_app = FaceAnalysis(allowed_modules=['detection'])
                    face_app.prepare(ctx_id=-1, det_size=det_size)
                    print(f"[face_pipeline] Initialized with CPU fallback, det_size={det_size}")
                except Exception as cpu_error:
                    raise RuntimeError(f"Failed to initialize face pipeline (GPU and CPU): {cpu_error}") from cpu_error
            else:
                raise


def _get_face_app_for_stream(stream_id: Optional[str] = None):
    """Get appropriate face_app instance for a stream (distributes across GPUs)."""
    global face_app, face_apps, available_gpus
    
    if not face_apps:
        return face_app
    
    if not available_gpus:
        return face_app
    
    # Distribute streams across available GPUs using stream_id hash
    if stream_id:
        # Use hash of stream_id to consistently assign to same GPU
        gpu_idx = hash(stream_id) % len(available_gpus)
        selected_gpu = available_gpus[gpu_idx]
        return face_apps[selected_gpu]
    else:
        # Round-robin for streams without ID
        return face_apps[available_gpus[0]]


def _calculate_iou(bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int]) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        bbox1: (x1, y1, x2, y2)
        bbox2: (x1, y1, x2, y2)
    
    Returns:
        IoU value between 0 and 1
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2
    
    # Calculate intersection
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)
    
    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0
    
    intersection = (x2_i - x1_i) * (y2_i - y1_i)
    
    # Calculate union
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
    union = area1 + area2 - intersection
    
    if union == 0:
        return 0.0
    
    return intersection / union


def _match_detection_to_track(bbox: Tuple[int, int, int, int], 
                               tracks: Dict[int, Dict[str, Any]]) -> Optional[int]:
    """Match a detection to an existing track based on IoU.
    
    Args:
        bbox: Current detection bounding box (x1, y1, x2, y2)
        tracks: Dictionary of existing tracks (track_id -> tracking_info)
    
    Returns:
        track_id if match found, None otherwise
    """
    best_iou = 0.0
    best_track_id = None
    
    for track_id, track_info in tracks.items():
        track_bbox = track_info.get('bbox')
        if track_bbox is None:
            continue
        
        iou = _calculate_iou(bbox, track_bbox)
        if iou > best_iou and iou >= IOU_THRESHOLD:
            best_iou = iou
            best_track_id = track_id
    
    return best_track_id


def _cleanup_old_tracks(stream_id: str, current_frame_count: int, current_time: float):
    """Remove tracks that haven't been seen for too long.
    
    Args:
        stream_id: Stream identifier
        current_frame_count: Current frame number
        current_time: Current timestamp
    """
    global person_tracking
    
    if stream_id not in person_tracking:
        return
    
    tracks_to_remove = []
    tracks = person_tracking[stream_id]
    
    for track_id, track_info in tracks.items():
        last_seen = track_info.get('last_seen', 0)
        frame_count = track_info.get('frame_count', 0)
        frames_since_seen = current_frame_count - frame_count
        seconds_since_seen = current_time - last_seen
        
        # Remove if not seen for too long
        if frames_since_seen > MAX_TRACK_AGE_FRAMES or seconds_since_seen > MAX_TRACK_AGE_SECONDS:
            tracks_to_remove.append(track_id)
    
    for track_id in tracks_to_remove:
        del tracks[track_id]


def process_frame(frame_bgr: np.ndarray, force_process: bool = False, stream_id: Optional[str] = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Detect + recognize faces in one frame. Returns annotated frame + detections.
    
    Args:
        frame_bgr: Input BGR frame
        force_process: Deprecated - all frames are now processed (kept for backward compatibility)
        stream_id: Optional stream ID for frame buffer access and GPU assignment
    """
    global known_encodings, known_names, person_tracking, track_id_counter
    
    # Get appropriate face_app instance (distributed across GPUs if multiple available)
    current_face_app = _get_face_app_for_stream(stream_id)
    
    if current_face_app is None:
        raise RuntimeError("Face pipeline not initialized. Call init() first.")

    if frame_bgr is None:
        return frame_bgr, []

    # Initialize tracking for this stream if needed
    if stream_id:
        if stream_id not in person_tracking:
            person_tracking[stream_id] = {}
        if stream_id not in track_id_counter:
            track_id_counter[stream_id] = 0
    
    # Track frame count and time for cleanup
    current_time = time.time()
    frame_count_key = f"{stream_id}_frame_count" if stream_id else "default_frame_count"
    if not hasattr(process_frame, '_frame_counts'):
        process_frame._frame_counts = {}
    if frame_count_key not in process_frame._frame_counts:
        process_frame._frame_counts[frame_count_key] = 0
    process_frame._frame_counts[frame_count_key] += 1
    current_frame_count = process_frame._frame_counts[frame_count_key]
    
    # Cleanup old tracks periodically
    if stream_id and current_frame_count % 10 == 0:  # Every 10 frames
        with tracking_lock:
            _cleanup_old_tracks(stream_id, current_frame_count, current_time)

    # Process every frame - no skipping for maximum face capture quality

    # Optimized for Tesla T4 GPU: Process at full HD resolution for maximum quality
    # Tesla T4 can handle full resolution processing efficiently
    original_h, original_w = frame_bgr.shape[:2]
    max_width = 1920  # Process full HD resolution (Tesla T4 optimized)
    
    if original_w > max_width:
        scale = max_width / original_w
        new_w = max_width
        new_h = int(original_h * scale)
        # Use faster interpolation for real-time processing
        scaled_frame = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        scale_back = original_w / new_w
    else:
        scaled_frame = frame_bgr
        scale_back = 1.0
        new_w, new_h = original_w, original_h

    h, w = new_h, new_w
    faces = current_face_app.get(scaled_frame)
    detections: List[Dict[str, Any]] = []
    
    # Get tracks for this stream (ensure it exists)
    if stream_id:
        if stream_id not in person_tracking:
            with tracking_lock:
                if stream_id not in person_tracking:
                    person_tracking[stream_id] = {}
        tracks = person_tracking[stream_id]
    else:
        tracks = {}

    for f in faces:
        # InsightFace bbox order: [x1, y1, x2, y2]
        try:
            x1, y1, x2, y2 = map(int, f.bbox)
        except Exception:
            bbox = getattr(f, "bbox", None)
            if bbox is None or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])

        # Scale bbox back to original frame size if we downscaled
        if scale_back != 1.0:
            x1 = int(x1 * scale_back)
            x2 = int(x2 * scale_back)
            y1 = int(y1 * scale_back)
            y2 = int(y2 * scale_back)
            w, h = original_w, original_h

        # Clamp to original image bounds
        x1 = max(0, min(w - 1, x1))
        x2 = max(0, min(w - 1, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(0, min(h - 1, y2))

        # Skip tiny boxes
        if (x2 - x1) < 20 or (y2 - y1) < 20:
            continue

        # Crop face from original frame (not downscaled)
        face_crop_bgr = frame_bgr[y1:y2, x1:x2]
        if face_crop_bgr.size == 0:
            continue

        # Skip very small faces (likely false positives) - slightly more lenient for streaming
        if (x2 - x1) < 25 or (y2 - y1) < 25:
            continue

        face_crop_rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)

        # Provide location relative to crop for speed (num_jitters=0 for speed)
        crop_h, crop_w = face_crop_rgb.shape[:2]
        crop_location = [(0, crop_w - 1, crop_h - 1, 0)]
        try:
            # Use num_jitters=0 and small model for faster encoding (optimized for real-time)
            encs = face_recognition.face_encodings(
                face_crop_rgb, 
                known_face_locations=crop_location, 
                num_jitters=0,  # No jittering for speed
                model='small'    # Small model for faster processing
            )
        except Exception as e:
            # Silently skip encoding errors to avoid log spam
            encs = []

        # Get current bounding box
        current_bbox = (x1, y1, x2, y2)
        
        # Try to match this detection to an existing track
        matched_track_id = None
        persisted_name = None
        
        if stream_id and tracks:
            with tracking_lock:
                # Make a copy of track IDs to iterate safely
                track_ids = list(tracks.keys())
                matched_track_id = _match_detection_to_track(current_bbox, tracks)
                if matched_track_id is not None:
                    # Found a match - get persisted name
                    track_info = tracks[matched_track_id]
                    persisted_name = track_info.get('name')
        
        # Initialize name: use persisted name if it's a known person, otherwise "Unknown"
        # Once a person is recognized as known, we keep that name
        if persisted_name and persisted_name != "Unknown":
            name = persisted_name
        else:
            name = "Unknown"
        
        conf = 0.0
        
        # Get InsightFace detection confidence (how confident the detector is that it found a face)
        det_conf = getattr(f, "det_score", None) or getattr(f, "score", None)
        if det_conf is None:
            det_conf = 0.0
        else:
            det_conf = float(det_conf)

        # Try to recognize the face
        recognized_name = None
        face_encoding = None
        
        if encs and len(known_encodings) > 0:
            enc = encs[0]
            face_encoding = enc  # Store for tracking
            distances = face_recognition.face_distance(known_encodings, enc)
            best_idx = int(np.argmin(distances))
            best_dist = float(distances[best_idx])
            recog_conf = max(0.0, 1.0 - best_dist)
            if best_dist <= TOLERANCE:
                recognized_name = known_names[best_idx]
                # If we recognized a known person, use that name (this overrides "Unknown" but not existing known names)
                if recognized_name and recognized_name != "Unknown":
                    name = recognized_name
                    # For known faces, use recognition confidence (how well it matches)
                    conf = recog_conf
                else:
                    # Shouldn't happen, but handle it
                    conf = det_conf
            else:
                # Recognition failed - keep current name (persisted known name or "Unknown")
                conf = det_conf
        else:
            # No encoding or no known faces - keep current name (persisted known name or "Unknown")
            conf = det_conf
        
        # Update or create tracking entry
        if stream_id:
            with tracking_lock:
                if matched_track_id is not None:
                    # Update existing track
                    track_info = tracks[matched_track_id]
                    track_info['bbox'] = current_bbox
                    track_info['last_seen'] = current_time
                    # Update name only if we recognized a known person (never change from known to Unknown)
                    if recognized_name and recognized_name != "Unknown":
                        track_info['name'] = recognized_name
                    # Update encoding if available
                    if face_encoding is not None:
                        track_info['encoding'] = face_encoding
                else:
                    # Create new track
                    track_id = track_id_counter[stream_id]
                    track_id_counter[stream_id] += 1
                    tracks[track_id] = {
                        'name': name,  # Can be "Unknown" initially, but will be updated if recognized
                        'bbox': current_bbox,
                        'last_seen': current_time,
                        'frame_count': current_frame_count,
                        'encoding': face_encoding if face_encoding is not None else None
                    }

        # Save face crop asynchronously to avoid blocking frame processing
        # Try to get best frame from buffer for sharp capture
        def _save_face_async():
            try:
                save_label = name if name != "Unknown" else "unknown"
                
                # save_face_image will automatically get sharpest frame from buffer if stream_id provided
                # Save with more context (like original frame) - no aggressive cropping/upscaling
                save_face_image(
                    frame_bgr=frame_bgr.copy(),
                    bbox=(x1, y1, x2, y2),
                    label=save_label,
                    confidence=conf,
                    min_interval=MIN_SAVE_INTERVAL,
                    source="stream",
                    expand_factor=1.0,   # 100% expansion - capture full context like original frame
                    target_width=None,  # No forced upscaling - preserve natural resolution
                    max_upscale=1.2,   # Minimal upscaling only for very small faces (max 20%)
                    jpeg_quality=95,   # High quality JPEG without over-compression
                    stream_id=stream_id,  # Pass stream_id to access frame buffer
                    prefer_png=False
                )
            except Exception as e:
                print(f"Error saving face in async thread: {e}")
        
        # Spawn thread to save face without blocking frame processing
        save_thread = threading.Thread(target=_save_face_async, daemon=True)
        save_thread.start()

        # Draw and store
        cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = f"{name} ({conf:.2f})"
        label_y = y1 - 10 if y1 - 10 > 10 else y1 + 10
        cv2.putText(
            frame_bgr,
            label,
            (x1, label_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2,
        )
        detections.append({"name": name, "conf": conf, "bbox": (x1, y1, x2, y2)})

    return frame_bgr, detections