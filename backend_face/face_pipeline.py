# face_pipeline.py
"""
Face Detection and Recognition Pipeline using InsightFace + face_recognition

KEY FEATURES:
1. Face Detection: InsightFace (RetinaFace detector) - Fast and accurate
2. Face Recognition: face_recognition library (dlib-based)
3. NMS (Non-Maximum Suppression): Eliminates overlapping bounding boxes
4. GPU Acceleration: Automatic GPU/CPU fallback

CRITICAL FIX - Overlapping Bounding Boxes:
The InsightFace detector can produce multiple overlapping detections for the same face,
especially during movement. This causes:
- Multiple boxes on one person
- Ghost boxes in empty spaces when person moves
- Confusing visual output

SOLUTION: Apply Non-Maximum Suppression (NMS) after detection to keep only the
best bounding box for each face and remove overlapping duplicates.
"""
import cv2
import numpy as np
import face_recognition
from insightface.app import FaceAnalysis
from typing import List, Tuple, Dict, Any, Optional
import threading
import os
from save_face import save_face_image

# ============================================================================
# CONFIGURATION PARAMETERS - Adjust these for your use case
# ============================================================================

# Face Recognition Tolerance: Lower = more strict matching
TOLERANCE = 0.47  # Was 0.5, now more selective (range: 0.0-1.0)

# Rate limit for saving same face per label (seconds)
MIN_SAVE_INTERVAL = 5.0

# Performance: Process every Nth frame for real-time streaming
PROCESS_EVERY_N_FRAMES = 2  # Process every 2nd frame (30fps -> 15fps processing)
FRAME_COUNTER = 0

# NMS (Non-Maximum Suppression) - CRITICAL for eliminating overlapping boxes
# Lower threshold = more aggressive at removing overlaps
# Recommended range: 0.3-0.5 for face detection
# 0.3 = strict (remove boxes with >30% overlap)
# 0.5 = moderate (remove boxes with >50% overlap)
NMS_IOU_THRESHOLD = 0.3

# ============================================================================

# Initialize detector and known faces (singleton-like)
face_app = None
known_encodings: List[np.ndarray] = []
known_names: List[str] = []


def check_gpu_availability() -> int:
    """Check if GPU is available for InsightFace/ONNXRuntime."""
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        if 'CUDAExecutionProvider' in providers:
            # Try to create a simple session to verify CUDA works
            try:
                # Check if CUDA libraries are accessible
                test_providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
                print(f"[INFO] ONNX providers available: {providers}")
                return 0  # GPU device ID
            except Exception as e:
                print(f"[WARN] CUDA provider available but may have library issues: {e}")
                print("[INFO] Falling back to CPU")
                return -1
        else:
            print(f"[INFO] CUDA provider not available. Available providers: {providers}")
            return -1
    except ImportError:
        print("[WARN] onnxruntime not available")
        return -1
    except Exception as e:
        print(f"[WARN] Error checking GPU availability: {e}")
        return -1


def calculate_iou(bbox1: Tuple[int, int, int, int], bbox2: Tuple[int, int, int, int]) -> float:
    """Calculate Intersection over Union (IoU) between two bounding boxes.
    
    Args:
        bbox1: (x1, y1, x2, y2) format
        bbox2: (x1, y1, x2, y2) format
    
    Returns:
        IoU value between 0.0 and 1.0
    """
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2
    
    # Calculate intersection rectangle
    x1_i = max(x1_1, x1_2)
    y1_i = max(y1_1, y1_2)
    x2_i = min(x2_1, x2_2)
    y2_i = min(y2_1, y2_2)
    
    # No intersection
    if x2_i <= x1_i or y2_i <= y1_i:
        return 0.0
    
    # Calculate areas
    intersection_area = (x2_i - x1_i) * (y2_i - y1_i)
    bbox1_area = (x2_1 - x1_1) * (y2_1 - y1_1)
    bbox2_area = (x2_2 - x1_2) * (y2_2 - y1_2)
    union_area = bbox1_area + bbox2_area - intersection_area
    
    # Avoid division by zero
    if union_area == 0:
        return 0.0
    
    return intersection_area / union_area


def apply_nms(faces: List[Any], iou_threshold: float = 0.3) -> List[Any]:
    """Apply Non-Maximum Suppression to eliminate overlapping face detections.
    
    This is critical to prevent multiple bounding boxes on the same face.
    InsightFace detector can produce overlapping detections, especially during movement.
    
    Args:
        faces: List of face detections from InsightFace (each has .bbox and .det_score)
        iou_threshold: IoU threshold for considering boxes as overlapping (0.3 = aggressive)
    
    Returns:
        Filtered list of faces with overlaps removed
    """
    if len(faces) <= 1:
        return faces
    
    # Extract bounding boxes and scores
    boxes = []
    scores = []
    for f in faces:
        try:
            bbox = f.bbox
            if bbox is None or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            boxes.append((x1, y1, x2, y2))
            # InsightFace provides det_score (detection confidence)
            score = float(getattr(f, 'det_score', 1.0))
            scores.append(score)
        except Exception:
            continue
    
    if len(boxes) == 0:
        return []
    
    # Convert to numpy arrays for efficient processing
    boxes = np.array(boxes)
    scores = np.array(scores)
    
    # Sort by score (highest first)
    sorted_indices = np.argsort(scores)[::-1]
    
    keep_indices = []
    suppressed = set()
    
    for i in sorted_indices:
        if i in suppressed:
            continue
        
        keep_indices.append(i)
        
        # Suppress all boxes with high IoU with this box
        for j in sorted_indices:
            if j == i or j in suppressed:
                continue
            
            iou = calculate_iou(
                tuple(boxes[i]),
                tuple(boxes[j])
            )
            
            if iou > iou_threshold:
                suppressed.add(j)
    
    # Return faces in kept indices
    filtered_faces = [faces[i] for i in keep_indices]
    
    return filtered_faces


def set_nms_threshold(threshold: float) -> None:
    """
    Adjust NMS IoU threshold at runtime.
    
    Args:
        threshold: IoU threshold (0.0-1.0). Lower = more aggressive overlap removal.
                   Recommended: 0.3-0.5 for face detection
    """
    global NMS_IOU_THRESHOLD
    if 0.0 <= threshold <= 1.0:
        NMS_IOU_THRESHOLD = threshold
        print(f"[face_pipeline] NMS IoU threshold updated to {threshold}")
    else:
        print(f"[WARN] Invalid NMS threshold {threshold}, must be between 0.0 and 1.0")


def get_detector_info() -> Dict[str, Any]:
    """
    Get information about the face detection configuration.
    
    Returns:
        Dictionary with detector settings
    """
    global face_app, NMS_IOU_THRESHOLD, TOLERANCE
    
    info = {
        "detector": "InsightFace (RetinaFace)",
        "recognition": "face_recognition (dlib)",
        "nms_enabled": True,
        "nms_iou_threshold": NMS_IOU_THRESHOLD,
        "recognition_tolerance": TOLERANCE,
        "frame_skip": PROCESS_EVERY_N_FRAMES,
        "initialized": face_app is not None
    }
    
    if face_app is not None:
        info["detection_size"] = getattr(face_app, 'det_size', 'unknown')
        info["device"] = "GPU" if getattr(face_app, 'ctx_id', -1) >= 0 else "CPU"
    
    return info


def init(data_dir: str, ctx: int = -1, det_size: Tuple[int, int] = (640, 640)) -> None:
    """Initialize known faces and InsightFace detector with GPU detection."""
    global face_app, known_encodings, known_names

    # Reuse your function from fr1.py
    try:
        from fr1 import load_known_faces
    except Exception as e:
        raise ImportError("Cannot import load_known_faces from fr1.py") from e

    known_encodings, known_names = load_known_faces(data_dir)

    # Auto-detect GPU if ctx is 0 but GPU might not be available
    if ctx == 0:
        detected_ctx = check_gpu_availability()
        if detected_ctx == -1:
            print("[WARN] GPU requested but not available, using CPU")
            ctx = -1
        else:
            print("[INFO] Using GPU for face detection")
    elif ctx == -1:
        print("[INFO] Using CPU for face detection")

    try:
        face_app = FaceAnalysis(allowed_modules=['detection'], providers=['CPUExecutionProvider'])
        face_app.prepare(ctx_id=ctx, det_size=det_size)
        
        # Configure detection threshold if supported (helps reduce false positives)
        # InsightFace uses det_thresh for detection confidence threshold
        # Higher threshold = fewer false positives, but might miss some faces
        # Default is usually 0.5, we keep it moderate for good balance
        if hasattr(face_app, 'det_thresh'):
            face_app.det_thresh = 0.5  # Moderate threshold for good detection
        
        print(f"[face_pipeline] Initialized successfully with ctx={ctx}, det_size={det_size}")
        print(f"[face_pipeline] NMS enabled with IoU threshold={NMS_IOU_THRESHOLD}")
    except Exception as e:
        # If GPU init fails, try CPU
        if ctx != -1:
            print(f"[WARN] GPU initialization failed: {e}")
            print("[INFO] Falling back to CPU")
            try:
                face_app = FaceAnalysis(allowed_modules=['detection'], providers=['CPUExecutionProvider'])
                face_app.prepare(ctx_id=-1, det_size=det_size)
                
                if hasattr(face_app, 'det_thresh'):
                    face_app.det_thresh = 0.5
                
                print(f"[face_pipeline] Initialized with CPU fallback, det_size={det_size}")
                print(f"[face_pipeline] NMS enabled with IoU threshold={NMS_IOU_THRESHOLD}")
            except Exception as cpu_error:
                raise RuntimeError(f"Failed to initialize face pipeline (GPU and CPU): {cpu_error}") from cpu_error
        else:
            raise


def process_frame(frame_bgr: np.ndarray, force_process: bool = False, stream_id: Optional[str] = None) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Detect + recognize faces in one frame. Returns annotated frame + detections.
    
    Args:
        frame_bgr: Input BGR frame
        force_process: If True, process this frame regardless of frame skipping
    """
    global face_app, known_encodings, known_names, FRAME_COUNTER

    if face_app is None:
        raise RuntimeError("Face pipeline not initialized. Call init() first.")

    if frame_bgr is None:
        return frame_bgr, []

    # Frame skipping for performance: only process every Nth frame
    if not force_process:
        FRAME_COUNTER += 1
        if FRAME_COUNTER % PROCESS_EVERY_N_FRAMES != 0:
            # Return frame without processing but keep detections from last processed frame
            return frame_bgr, []

    # Downscale frame for faster processing while maintaining quality
    # Reduced max width for better performance during streaming
    original_h, original_w = frame_bgr.shape[:2]
    max_width = 960  # Reduced from 1280 for better performance (still good quality)
    
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
    faces_raw = face_app.get(scaled_frame)
    
    # CRITICAL: Apply Non-Maximum Suppression to eliminate overlapping bounding boxes
    # InsightFace detector can produce multiple overlapping detections for the same face,
    # especially during movement. This eliminates duplicates and ghost boxes.
    faces = apply_nms(faces_raw, iou_threshold=NMS_IOU_THRESHOLD)
    
    # Debug logging when NMS filters out overlapping boxes
    if len(faces_raw) > len(faces):
        removed_count = len(faces_raw) - len(faces)
        print(f"[NMS] Removed {removed_count} overlapping detection(s) from {len(faces_raw)} total")
    
    detections: List[Dict[str, Any]] = []

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

        name = "Unknown"
        conf = 0.0

        if encs and len(known_encodings) > 0:
            enc = encs[0]
            distances = face_recognition.face_distance(known_encodings, enc)
            best_idx = int(np.argmin(distances))
            best_dist = float(distances[best_idx])
            conf = max(0.0, 1.0 - best_dist)
            if best_dist <= TOLERANCE:
                name = known_names[best_idx]

        # Save face crop asynchronously to avoid blocking frame processing
        # Try to get best frame from buffer for sharp capture
        def _save_face_async():
            try:
                save_label = name if name != "Unknown" else "unknown"
                
                # save_face_image will automatically get sharpest frame from buffer if stream_id provided
                save_face_image(
                    frame_bgr=frame_bgr.copy(),
                    bbox=(x1, y1, x2, y2),
                    label=save_label,
                    confidence=conf,
                    min_interval=MIN_SAVE_INTERVAL,
                    source="stream",
                    expand_factor=0.4,  # 40% expansion for better context
                    target_width=800,   # Higher resolution for better clarity (increased from 640)
                    max_upscale=2.5,    # Allow more upscaling for small faces
                    jpeg_quality=99,    # Very high quality JPEG
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
            0.5,
            (255, 255, 255),
            2,
        )
        detections.append({"name": name, "conf": conf, "bbox": (x1, y1, x2, y2)})

    return frame_bgr, detections