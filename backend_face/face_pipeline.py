# face_pipeline.py
import cv2
import numpy as np
import face_recognition
from insightface.app import FaceAnalysis
from typing import List, Tuple, Dict, Any
import threading
from save_face import save_face_image

TOLERANCE = 0.47 # Stricter matching (lower = more strict). Was 0.5, now more selective
# Rate limit for saving same face per label (seconds)
MIN_SAVE_INTERVAL = 5.0

# Initialize detector and known faces (singleton-like)
face_app = None
known_encodings: List[np.ndarray] = []
known_names: List[str] = []


def init(data_dir: str, ctx: int = -1, det_size: Tuple[int, int] = (640, 640)) -> None:
    """Initialize known faces and InsightFace detector."""
    global face_app, known_encodings, known_names

    # Reuse your function from fr1.py
    try:
        from fr1 import load_known_faces
    except Exception as e:
        raise ImportError("Cannot import load_known_faces from fr1.py") from e

    known_encodings, known_names = load_known_faces(data_dir)

    face_app = FaceAnalysis(allowed_modules=['detection'])
    face_app.prepare(ctx_id=ctx, det_size=det_size)
    print("[face_pipeline] Initialized successfully.")


def process_frame(frame_bgr: np.ndarray) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """Detect + recognize faces in one frame. Returns annotated frame + detections."""
    global face_app, known_encodings, known_names

    if face_app is None:
        raise RuntimeError("Face pipeline not initialized. Call init() first.")

    if frame_bgr is None:
        return frame_bgr, []

    h, w = frame_bgr.shape[:2]
    faces = face_app.get(frame_bgr)
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

        # Clamp to image bounds
        x1 = max(0, min(w - 1, x1))
        x2 = max(0, min(w - 1, x2))
        y1 = max(0, min(h - 1, y1))
        y2 = max(0, min(h - 1, y2))

        # Skip tiny boxes
        if (x2 - x1) < 20 or (y2 - y1) < 20:
            continue

        # Crop face and encode
        face_crop_bgr = frame_bgr[y1:y2, x1:x2]
        if face_crop_bgr.size == 0:
            continue

        face_crop_rgb = cv2.cvtColor(face_crop_bgr, cv2.COLOR_BGR2RGB)

        # Provide location relative to crop for speed
        crop_h, crop_w = face_crop_rgb.shape[:2]
        crop_location = [(0, crop_w - 1, crop_h - 1, 0)]
        try:
            encs = face_recognition.face_encodings(
                face_crop_rgb, known_face_locations=crop_location, num_jitters=0
            )
        except Exception:
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
        def _save_face_async():
            try:
                save_label = name if name != "Unknown" else "unknown"
                # Pass frame + bbox for robust cropping with padding and expansion
                save_face_image(
                    frame_bgr=frame_bgr,
                    bbox=(x1, y1, x2, y2),
                    label=save_label,
                    confidence=conf,
                    min_interval=MIN_SAVE_INTERVAL,
                    source="stream",
                    expand_factor=0.5,  # 50% expansion for better context
                    target_width=512,   # Higher resolution target
                    max_upscale=1.5,    # Conservative upscaling to preserve quality
                    jpeg_quality=98     # Very high quality JPEG
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