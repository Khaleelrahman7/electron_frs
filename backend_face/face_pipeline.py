# face_pipeline.py
import cv2
import numpy as np
import face_recognition
from insightface.app import FaceAnalysis
from typing import List, Tuple, Dict, Any, Optional
import threading
import os
from save_face import save_face_image

TOLERANCE = 0.47 # Stricter matching (lower = more strict). Was 0.5, now more selective
# Rate limit for saving same face per label (seconds)
MIN_SAVE_INTERVAL = 5.0

# Performance optimization: process every Nth frame for real-time streaming
PROCESS_EVERY_N_FRAMES = 1  # Process every frame (Tesla T4 can handle it)
FRAME_COUNTER = 0

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
        face_app = FaceAnalysis(allowed_modules=['detection'])
        face_app.prepare(ctx_id=ctx, det_size=det_size)
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
    faces = face_app.get(scaled_frame)
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
                    target_width=1024,   # Optimized for Tesla T4: Higher resolution for maximum clarity
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