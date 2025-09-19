from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
import os
import shutil
from typing import List, Optional
from datetime import datetime
import logging
import face_recognition
import cv2
import numpy as np
from .config import KNOWN_FACES_DIR, UNKNOWN_FACES_DIR

# API base URL for constructing image URLs
API_BASE_URL = "http://localhost:8000"

def convert_file_path_to_url(file_path: str) -> str:
    """Convert a file path to an HTTP URL for serving images"""
    try:
        # Normalize the path
        file_path = os.path.normpath(file_path)

        # Check if it's a known or unknown face
        if "known" in file_path:
            # Extract components for known faces: camera/person/image
            parts = file_path.split(os.sep)
            known_idx = parts.index("known")
            if len(parts) > known_idx + 3:
                camera = parts[known_idx + 1]
                person = parts[known_idx + 2]
                image_name = parts[known_idx + 3]
                return f"{API_BASE_URL}/api/captured/image/known/{camera}/{person}/{image_name}"
        elif "unknown" in file_path:
            # Extract components for unknown faces: camera/image
            parts = file_path.split(os.sep)
            unknown_idx = parts.index("unknown")
            if len(parts) > unknown_idx + 2:
                camera = parts[unknown_idx + 1]
                image_name = parts[unknown_idx + 2]
                return f"{API_BASE_URL}/api/captured/image/unknown/{camera}/unknown/{image_name}"

        # Fallback: return the original path (shouldn't happen in normal cases)
        return file_path
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
    camera: Optional[str] = Query("all_cameras", description="Filter by camera")
):
    """Filter faces by name, date range, and camera."""
    # Validate date range if both dates are provided
    if from_date and to_date:
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt = datetime.strptime(to_date, "%Y-%m-%d")
            if from_dt > to_dt:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid date range: from_date cannot be later than to_date"
                )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid date format. Please use YYYY-MM-DD format: {str(e)}"
            )

    matching_faces = []
    
    # Helper function to process a directory
    def process_directory(base_dir, face_type):
        if not os.path.exists(base_dir):
            return []
            
        faces = []
        for camera_dir in os.listdir(base_dir):
            camera_path = os.path.join(base_dir, camera_dir)
            if not os.path.isdir(camera_path):
                continue
                
            # Skip if camera filter is set and doesn't match
            if camera != "all_cameras" and camera_dir != camera:
                continue
                
            # For known faces, process person directories
            if face_type == "known":
                for person_dir in os.listdir(camera_path):
                    person_path = os.path.join(camera_path, person_dir)
                    if not os.path.isdir(person_path):
                        continue
                        
                    # Skip if name filter is set and doesn't match
                    if name and name.lower() not in person_dir.lower():
                        continue
                        
                    for face_file in os.listdir(person_path):
                        img_path = os.path.join(person_path, face_file)
                        if not os.path.isfile(img_path):
                            continue
                            
                        try:
                            timestamp_str = face_file.split('_', 1)[1].rsplit('.', 1)[0]
                            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                            
                            # Apply date filters
                            if from_date and timestamp < datetime.strptime(from_date, "%Y-%m-%d"):
                                continue
                            if to_date and timestamp > datetime.strptime(to_date, "%Y-%m-%d"):
                                continue
                                
                            faces.append({
                                "name": person_dir,
                                "image_path": convert_file_path_to_url(img_path),
                                "timestamp": timestamp.isoformat(),
                                "type": "known",
                                "camera": camera_dir
                            })
                        except (ValueError, IndexError) as e:
                            logger.warning(f"Error processing file {face_file}: {e}")
                            continue
                            
            # For unknown faces, process directly in camera directory
            else:
                for face_file in os.listdir(camera_path):
                    img_path = os.path.join(camera_path, face_file)
                    if not os.path.isfile(img_path):
                        continue
                        
                    try:
                        timestamp_str = face_file.split('_', 1)[1].rsplit('.', 1)[0]
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        
                        # Apply date filters
                        if from_date and timestamp < datetime.strptime(from_date, "%Y-%m-%d"):
                            continue
                        if to_date and timestamp > datetime.strptime(to_date, "%Y-%m-%d"):
                            continue
                            
                        faces.append({
                            "name": "Unknown",
                            "image_path": convert_file_path_to_url(img_path),
                            "timestamp": timestamp.isoformat(),
                            "type": "unknown",
                            "camera": camera_dir
                        })
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Error processing file {face_file}: {e}")
                        continue
                        
        return faces
    
    # Process known faces
    known_faces = process_directory(KNOWN_FACES_DIR, "known")
    matching_faces.extend(known_faces)
    
    # Process unknown faces
    unknown_faces = process_directory(UNKNOWN_FACES_DIR, "unknown")
    matching_faces.extend(unknown_faces)
    
    # Sort faces by timestamp (newest first)
    matching_faces.sort(key=lambda x: x["timestamp"], reverse=True)
    
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
                                matches = face_recognition.compare_faces([face_encoding], known_face_encoding, tolerance=0.6)
                                if matches[0]:
                                    # Calculate face distance (lower is better)
                                    face_distance = face_recognition.face_distance([face_encoding], known_face_encoding)[0]
                                    confidence = 1 - face_distance
                                    
                                    # Only include matches with confidence >= 50%
                                    if confidence >= 0.5:
                                        # Get person name from directory structure
                                        person_name = os.path.basename(os.path.dirname(img_path))
                                        
                                        # Get timestamp from filename
                                        timestamp_str = file.split('_', 1)[1].rsplit('.', 1)[0]
                                        try:
                                            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                                        except ValueError:
                                            timestamp = datetime.fromtimestamp(os.path.getctime(img_path))
                                        
                                        matching_faces.append(FaceMatch(
                                            image_path=img_path,
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
