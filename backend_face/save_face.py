import os
from pathlib import Path
import time
from datetime import datetime
import csv
import threading
import re
import cv2
import numpy as np
from typing import Optional, Dict, Tuple

# CONFIG - Use dynamic path based on file location
# Get the backend_face directory (parent of this file's directory)
BACKEND_FACE_DIR = Path(__file__).parent.absolute()
BASE_DIR = BACKEND_FACE_DIR / "captured_faces"
KNOWN_DIRNAME = "known"
UNKNOWN_DIRNAME = "unknown"
LOG_CSV = BASE_DIR / "capture_log.csv"
# Minimum seconds between saves for same label (to avoid duplicates)
DEFAULT_MIN_SAVE_INTERVAL_SECONDS = 5.0

# Internal state for rate-limiting and thread-safety
_last_saved_time: Dict[str, float] = {}
_lock = threading.Lock()

# sanitize label for filename and directory name
_filename_safe_re = re.compile(r"[^\w\-_.]")

def sanitize_label(label: str) -> str:
    if not label:
        return "unknown"
    label = label.strip().lower()
    label = label.replace(" ", "_")
    label = _filename_safe_re.sub("", label)
    if label == "":
        return "unknown"
    return label

def ensure_dirs_for_label(label: str) -> Path:
    label_s = sanitize_label(label)
    if label_s == "unknown":
        dir_path = BASE_DIR / UNKNOWN_DIRNAME
    else:
        dir_path = BASE_DIR / KNOWN_DIRNAME / label_s
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path

def _current_timestamp_str() -> str:
    # e.g. 20251029_153012_123456
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

def _should_save(label: str, min_interval: float) -> bool:
    label_s = sanitize_label(label)
    now = time.time()
    with _lock:
        last = _last_saved_time.get(label_s, 0.0)
        if now - last >= min_interval:
            _last_saved_time[label_s] = now
            return True
        return False

def _append_log(row: dict):
    header = ["filename", "label", "timestamp_iso", "saved_path", "confidence", "source"]
    write_header = not LOG_CSV.exists()
    try:
        LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
        with LOG_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=header)
            if write_header:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in header})
    except Exception as e:
        # don't crash pipeline for logging issues; just print
        print("Failed to write capture log:", e)

def _bbox_to_ltrb(bbox: Tuple, frame_shape: Tuple) -> Tuple[int, int, int, int]:
    """
    Auto-detect bbox format and convert to (left, top, right, bottom).
    Handles: normalized coords [0..1], (x,y,w,h) in pixels, or (l,t,r,b) coords.
    Returns: (l, t, r, b) clamped to image bounds.
    """
    H, W = frame_shape[0], frame_shape[1]
    x0, x1, x2, x3 = bbox
    
    # Check if all values are normalized (0..1)
    if 0 <= x0 <= 1 and 0 <= x1 <= 1 and 0 <= x2 <= 1 and 0 <= x3 <= 1:
        # Treat as normalized (x,y,w,h)
        x = int(x0 * W)
        y = int(x1 * H)
        w = int(x2 * W)
        h = int(x3 * H)
        l, t, r, b = x, y, x + w, y + h
        return max(0, l), max(0, t), min(W, r), min(H, b)
    
    # Check if looks like (x,y,w,h) in pixels
    if x2 > 0 and x3 > 0 and (x0 + x2) <= W and (x1 + x3) <= H:
        l = int(x0)
        t = int(x1)
        r = int(x0 + x2)
        b = int(x1 + x3)
        return max(0, l), max(0, t), min(W, r), min(H, b)
    
    # Treat as (l,t,r,b) if they look like coords
    if x2 > x0 and x3 > x1 and x2 <= W and x3 <= H:
        l = int(x0)
        t = int(x1)
        r = int(x2)
        b = int(x3)
        return max(0, l), max(0, t), min(W, r), min(H, b)
    
    # Fallback: clamp and validate
    l = int(np.clip(x0, 0, W - 1))
    t = int(np.clip(x1, 0, H - 1))
    r = int(np.clip(x2, 0, W - 1))
    b = int(np.clip(x3, 0, H - 1))
    if r <= l or b <= t:
        # Fallback to small box around center
        cx, cy = W // 2, H // 2
        s = min(W, H) // 4
        return cx - s, cy - s, cx + s, cy + s
    return l, t, r, b

def apply_clahe(image: np.ndarray) -> np.ndarray:
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) for enhancement."""
    try:
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        return enhanced
    except Exception:
        return image

def save_face_image(
    face_crop_bgr: Optional[np.ndarray] = None,
    frame_bgr: Optional[np.ndarray] = None,
    bbox: Optional[Tuple] = None,
    label: Optional[str] = None,
    confidence: Optional[float] = None,
    min_interval: float = DEFAULT_MIN_SAVE_INTERVAL_SECONDS,
    source: str = "stream",
    expand_factor: float = 0.5,
    target_width: int = 512,
    max_upscale: float = 1.5,
    jpeg_quality: int = 98
) -> Optional[Path]:
    """
    Robust face saving with auto-detected bbox format, smart padding, and limited upscaling.
    
    Can be called two ways:
    1. Direct crop: save_face_image(face_crop_bgr=crop, label="john", ...)
    2. Frame + bbox: save_face_image(frame_bgr=frame, bbox=(x1,y1,x2,y2), label="john", ...)
    
    Returns the saved Path or None if skipped/failed.
    """
    if face_crop_bgr is None and (frame_bgr is None or bbox is None):
        return None

    label = label or "unknown"
    label_s = sanitize_label(label)

    # rate limit
    if not _should_save(label_s, min_interval):
        return None

    try:
        # If bbox + frame provided, extract and expand crop
        if frame_bgr is not None and bbox is not None:
            H, W = frame_bgr.shape[:2]
            l, t, r, b = _bbox_to_ltrb(bbox, frame_bgr.shape)
            w_box = r - l
            h_box = b - t
            
            if w_box <= 0 or h_box <= 0:
                return None
            
            # Expand box by expand_factor to capture more context
            ew = int(w_box * expand_factor)
            eh = int(h_box * expand_factor)
            el = l - ew
            et = t - eh
            er = r + ew
            eb = b + eh
            
            # Calculate padding if expanded box goes outside image
            pad_left = max(0, -el)
            pad_top = max(0, -et)
            pad_right = max(0, er - W)
            pad_bottom = max(0, eb - H)
            
            # Clamp coords to image bounds
            el = max(0, el)
            et = max(0, et)
            er = min(W, er)
            eb = min(H, eb)
            
            face = frame_bgr[et:eb, el:er].copy()
            if face.size == 0:
                return None
            
            # Apply padding if needed using BORDER_REFLECT for better quality
            if any((pad_left, pad_top, pad_right, pad_bottom)):
                face = cv2.copyMakeBorder(
                    face, pad_top, pad_bottom, pad_left, pad_right,
                    borderType=cv2.BORDER_REFLECT_101
                )
            
            face_crop_bgr = face
        
        # Ensure dtype is uint8
        if face_crop_bgr.dtype != "uint8":
            face_crop_bgr = (face_crop_bgr * 255).astype("uint8") if face_crop_bgr.max() <= 1.0 else face_crop_bgr.astype("uint8")
        
        # Apply denoising first for better quality
        face_crop_bgr = cv2.fastNlMeansDenoisingColored(face_crop_bgr, None, 10, 10, 7, 21)
        
        # Smart resize: maintain aspect ratio, limit upscaling
        fh, fw = face_crop_bgr.shape[:2]
        aspect = fw / float(fh) if fh != 0 else 1.0
        desired_w = target_width
        desired_h = max(1, int(desired_w / aspect))
        
        # Limit upscaling to avoid heavy blur
        max_allowed_w = int(fw * max_upscale)
        if desired_w > max_allowed_w:
            desired_w = max_allowed_w
            desired_h = max(1, int(desired_w / aspect))
        
        # Choose interpolation based on scaling direction
        if desired_w > fw:
            # Upscaling - use high quality interpolation
            interpolation = cv2.INTER_CUBIC
        else:
            # Downscaling - use area interpolation for best quality
            interpolation = cv2.INTER_AREA
        
        # Only resize if it makes a noticeable difference
        if abs(desired_w - fw) > 2:
            face_crop_bgr = cv2.resize(
                face_crop_bgr, (desired_w, desired_h),
                interpolation=interpolation
            )
        
        # Apply gentle unsharp mask for clarity without artifacts
        gaussian = cv2.GaussianBlur(face_crop_bgr, (0, 0), 2.0)
        face_crop_bgr = cv2.addWeighted(face_crop_bgr, 1.5, gaussian, -0.5, 0)
        
        # Apply CLAHE for better contrast (reduced clip limit to avoid over-enhancement)
        face_crop_bgr = apply_clahe(face_crop_bgr)
        
        # Save
        dir_path = ensure_dirs_for_label(label_s)
        fname = f"{label_s}_{_current_timestamp_str()}.jpg"
        save_path = dir_path / fname
        
        success = cv2.imwrite(str(save_path), face_crop_bgr, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not success:
            print("cv2.imwrite failed for", save_path)
            return None
        
        # Log
        log_row = {
            "filename": fname,
            "label": label_s,
            "timestamp_iso": datetime.now().isoformat(),
            "saved_path": str(save_path),
            "confidence": confidence if confidence is not None else "",
            "source": source,
        }
        _append_log(log_row)
        return save_path
        
    except Exception as e:
        print("Error saving face image:", e)
        return None