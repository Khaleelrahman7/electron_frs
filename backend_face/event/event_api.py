from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
import os
import shutil
import re
from typing import List, Optional
from datetime import datetime
import logging
import face_recognition
import cv2
import numpy as np
from .config import KNOWN_FACES_DIR, UNKNOWN_FACES_DIR

# API base URL for constructing image URLs
# Defaults to localhost, can be overridden via environment variable
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8005")

def convert_file_path_to_url(file_path: str) -> str:
    try:
        normalized_path = os.path.normpath(file_path)
        known_root = os.path.normpath(KNOWN_FACES_DIR)
        unknown_root = os.path.normpath(UNKNOWN_FACES_DIR)

        if normalized_path.startswith(known_root):
            relative_path = os.path.relpath(normalized_path, known_root)
            parts = relative_path.split(os.sep)
            image_name = parts[-1]
            if len(parts) >= 3:
                camera_name = parts[0]
                person_name = parts[1]
                return f"{API_BASE_URL}/api/captured/image/known/{camera_name}/{person_name}/{image_name}"
            if len(parts) >= 2:
                person_name = parts[-2]
                return f"{API_BASE_URL}/api/captured/image/known/default/{person_name}/{image_name}"
            return f"{API_BASE_URL}/api/captured/image/known/default/default/{image_name}"

        if normalized_path.startswith(unknown_root):
            relative_path = os.path.relpath(normalized_path, unknown_root)
            parts = relative_path.split(os.sep)
            image_name = parts[-1]
            if len(parts) >= 2:
                camera_name = parts[0]
            else:
                camera_name = "default"
            return f"{API_BASE_URL}/api/captured/image/unknown/{camera_name}/unknown/{image_name}"

        return normalized_path
    except Exception as e:
        logger.warning(f"Error converting file path to URL: {file_path}, error: {e}")
        return file_path

router = APIRouter()

logger = logging.getLogger(__name__)

class FaceEvent(BaseModel):
    name: str
    image_path: str
    timestamp: str

class FaceMatch(BaseModel):
    image_path: str
    name: str
    confidence: float
    timestamp: str

@router.post("/known")
async def add_known_face(event: FaceEvent):
    """Add a known face event."""
    try:
        # Create camera directory if it doesn't exist
        camera_dir = os.path.join(KNOWN_FACES_DIR, "camera_1")
        os.makedirs(camera_dir, exist_ok=True)
        
        # Create person directory inside camera directory
        person_dir = os.path.join(camera_dir, event.name)
        os.makedirs(person_dir, exist_ok=True)
        
        # Move the image to the appropriate directory
        destination = os.path.join(person_dir, os.path.basename(event.image_path))
        shutil.move(event.image_path, destination)
        return {"message": "Known face added successfully"}
    except Exception as e:
        logger.error(f"Error adding known face: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unknown")
async def add_unknown_face(event: FaceEvent):
    """Add an unknown face event."""
    try:
        # Create camera directory if it doesn't exist
        camera_dir = os.path.join(UNKNOWN_FACES_DIR, "camera_1")
        os.makedirs(camera_dir, exist_ok=True)
        
        # Move the image to the appropriate directory
        destination = os.path.join(camera_dir, os.path.basename(event.image_path))
        shutil.move(event.image_path, destination)
        return {"message": "Unknown face added successfully"}
    except Exception as e:
        logger.error(f"Error adding unknown face: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cameras")
async def get_cameras():
    """Get list of available cameras from both known and unknown directories."""
    cameras = set()
    
    # Get cameras from known faces directory
    if os.path.exists(KNOWN_FACES_DIR):
        known_cameras = [d for d in os.listdir(KNOWN_FACES_DIR) 
                        if os.path.isdir(os.path.join(KNOWN_FACES_DIR, d)) 
                        and d.startswith('camera_')]
        cameras.update(known_cameras)
    
    # Get cameras from unknown faces directory
    if os.path.exists(UNKNOWN_FACES_DIR):
        unknown_cameras = [d for d in os.listdir(UNKNOWN_FACES_DIR) 
                          if os.path.isdir(os.path.join(UNKNOWN_FACES_DIR, d)) 
                          and d.startswith('camera_')]
        cameras.update(unknown_cameras)
    
    # Sort cameras numerically
    sorted_cameras = sorted(list(cameras), 
                          key=lambda x: int(x.split('_')[1]) if x.split('_')[1].isdigit() else float('inf'))
    
    return {"cameras": sorted_cameras}

@router.get("/filter")
async def filter_faces(
    name: Optional[str] = Query(None, description="Filter by name"),
    from_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    to_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    camera: Optional[str] = Query("all_cameras", description="Filter by camera"),
    face_type: Optional[str] = Query(None, description="Filter by face type: known or unknown")
):
    """Filter faces by name, date range, and camera."""
    name_filter = name.lower().strip() if name else None
    from_date_obj = None
    to_date_obj = None
    face_type_filter = None

    if face_type:
        normalized_face_type = face_type.lower().strip()
        if normalized_face_type not in {"known", "unknown"}:
            raise HTTPException(
                status_code=400,
                detail="Invalid face type. Allowed values are 'known' or 'unknown'"
            )
        face_type_filter = normalized_face_type

    try:
        if from_date:
            from_date_obj = datetime.strptime(from_date, "%Y-%m-%d").date()
        if to_date:
            to_date_obj = datetime.strptime(to_date, "%Y-%m-%d").date()
        if from_date_obj and to_date_obj and from_date_obj > to_date_obj:
            raise HTTPException(
                status_code=400,
                detail="Invalid date range: from_date cannot be later than to_date"
            )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format. Please use YYYY-MM-DD format: {exc}"
        ) from exc

    timestamp_regex = re.compile(r"(\d{8}_\d{6}(?:_\d{3,6})?)")

    def extract_timestamp(face_file: str, img_path: str) -> datetime:
        match = timestamp_regex.search(face_file)
        if match:
            raw = match.group(1)
            for fmt in ("%Y%m%d_%H%M%S_%f", "%Y%m%d_%H%M%S"):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue
        try:
            return datetime.fromtimestamp(os.path.getmtime(img_path))
        except Exception:
            return datetime.utcnow()

    def resolve_known_metadata(parts: List[str], face_file: str) -> tuple[str, str]:
        image_name = parts[-1] if parts else face_file
        if len(parts) >= 3:
            return parts[1], parts[0]
        if len(parts) >= 2:
            person = parts[-2]
            camera_name = parts[0] if parts[0].lower().startswith("camera_") else "default"
            return person, camera_name
        base_name = os.path.splitext(image_name)[0]
        match = timestamp_regex.search(base_name)
        if match:
            person = base_name[:match.start()].rstrip('_') or "Unknown"
        else:
            splits = base_name.split('_')
            person = splits[0] if splits else base_name
        return person, "default"

    def resolve_unknown_metadata(parts: List[str]) -> str:
        if len(parts) >= 2:
            return parts[0]
        return "default"

    def process_directory(base_dir: str, directory_type: str):
        if face_type_filter and face_type_filter != directory_type:
            return []
        if not os.path.exists(base_dir):
            return []
        faces = []
        for root_dir, _, files in os.walk(base_dir):
            for face_file in files:
                if not face_file.lower().endswith((".jpg", ".jpeg", ".png")):
                    continue
                img_path = os.path.join(root_dir, face_file)
                if not os.path.isfile(img_path):
                    continue

                timestamp = extract_timestamp(face_file, img_path)
                timestamp_date = timestamp.date()
                if from_date_obj and timestamp_date < from_date_obj:
                    continue
                if to_date_obj and timestamp_date > to_date_obj:
                    continue

                relative_path = os.path.relpath(img_path, base_dir)
                parts = relative_path.split(os.sep)

                if directory_type == "known":
                    person_name, camera_name = resolve_known_metadata(parts, face_file)
                    if name_filter and name_filter not in person_name.lower():
                        continue
                else:
                    camera_name = resolve_unknown_metadata(parts)
                    person_name = "Unknown"
                    if name_filter and name_filter not in "unknown":
                        continue

                if camera and camera != "all_cameras" and camera_name != camera:
                    continue

                faces.append({
                    "name": person_name,
                    "image_path": convert_file_path_to_url(img_path),
                    "timestamp": timestamp.isoformat(),
                    "type": directory_type,
                    "camera": camera_name
                })
        return faces

    matching_faces = []
    matching_faces.extend(process_directory(KNOWN_FACES_DIR, "known"))
    matching_faces.extend(process_directory(UNKNOWN_FACES_DIR, "unknown"))
    matching_faces.sort(key=lambda item: item["timestamp"], reverse=True)
    return matching_faces

@router.get("/directories")
async def get_directories():
    """Return the known and unknown faces directories."""
    return {
        "known_faces_dir": KNOWN_FACES_DIR,
        "unknown_faces_dir": UNKNOWN_FACES_DIR
    }

@router.post("/match-face")
async def match_face(image: UploadFile = File(...)):
    """Match a face against the database of known faces."""
    try:
        # Read and process the uploaded image
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file")
            
        # Convert to RGB for face recognition
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Get face encodings
        face_locations = face_recognition.face_locations(img_rgb)
        if not face_locations:
            raise HTTPException(status_code=400, detail="No face detected in the image")
            
        face_encoding = face_recognition.face_encodings(img_rgb, face_locations)[0]
        
        # Find matching faces
        matching_faces = []
        
        # Walk through known faces directory
        for root, dirs, files in os.walk(KNOWN_FACES_DIR):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        # Load and process each image
                        img_path = os.path.join(root, file)
                        known_img = cv2.imread(img_path)
                        if known_img is None:
                            continue
                            
                        known_img_rgb = cv2.cvtColor(known_img, cv2.COLOR_BGR2RGB)
                        known_face_locations = face_recognition.face_locations(known_img_rgb)
                        
                        if known_face_locations:
                            known_face_encodings = face_recognition.face_encodings(known_img_rgb, known_face_locations)
                            
                            # Compare with uploaded face
                            for known_face_encoding in known_face_encodings:
                                # Compare faces
                                matches = face_recognition.compare_faces([face_encoding], known_face_encoding, tolerance=0.5)
                                if matches[0]:
                                    # Calculate face distance (lower is better)
                                    face_distance = face_recognition.face_distance([face_encoding], known_face_encoding)[0]
                                    confidence = 1 - face_distance
                                    
                                    # Only include matches with confidence >= 50%
                                    if confidence >= 0.53:
                                        # Get person name from directory structure
                                        person_name = os.path.basename(os.path.dirname(img_path))
                                        
                                        # Get timestamp from filename
                                        timestamp_str = file.split('_', 1)[1].rsplit('.', 1)[0]
                                        try:
                                            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                                        except ValueError:
                                            timestamp = datetime.fromtimestamp(os.path.getctime(img_path))
                                        
                                        matching_faces.append(FaceMatch(
                                            image_path=convert_file_path_to_url(img_path),
                                            name=person_name,
                                            confidence=float(confidence),
                                            timestamp=timestamp.isoformat()
                                        ))
                                    break  # Found a match for this image, move to next
                                    
                    except Exception as e:
                        logger.error(f"Error processing {file}: {str(e)}")
                        continue
        
        # Sort matching faces by confidence (highest first)
        matching_faces.sort(key=lambda x: x.confidence, reverse=True)
        
        return matching_faces
        
    except Exception as e:
        logger.error(f"Error matching face: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
