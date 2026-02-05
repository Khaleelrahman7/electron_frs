from datetime import timedelta
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from .security import authenticate_user, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from .users import create_user, get_user, list_users
from .storage import ensure_auth_data_dir

router = APIRouter(prefix="/auth", tags=["authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str
    role: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

class BootstrapSuperAdminRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    username: str
    role: str
    is_active: bool
    assigned_cameras: list
    assigned_menus: list

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    ensure_auth_data_dir()
    
    # Normalize username to lowercase
    username = request.username.lower()
    
    print(f"Login attempt: user='{username}', requested_role='{request.role}'")
    
    user = get_user(username)
    
    if not user:
        print(f"User not found: {username}")
        raise HTTPException(status_code=401, detail="Invalid credentials or role")

    print(f"User found: {username}, Actual Role: {user['role']}")

    # Authenticate using the user's ACTUAL role from the database.
    # This effectively ignores the role selected in the frontend dropdown,
    # preventing login failures due to role mismatch.
    auth_user = authenticate_user(username, request.password, user["role"])
    
    if not auth_user:
        print(f"Authentication failed for {username} (Password mismatch)")
        raise HTTPException(status_code=401, detail="Invalid credentials or role")
    
    print(f"Authentication successful for {username}")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": auth_user["username"], "role": auth_user["role"]},
        expires_delta=access_token_expires
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        role=auth_user["role"],
        username=auth_user["username"]
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user(request: Request):
    user = request.scope.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return UserResponse(
        username=user["username"],
        role=user["role"],
        is_active=user.get("is_active", True),
        assigned_cameras=user.get("assigned_cameras", []),
        assigned_menus=user.get("assigned_menus", [])
    )

@router.post("/bootstrap/superadmin")
async def bootstrap_superadmin(request: BootstrapSuperAdminRequest):
    """Create initial SuperAdmin user if none exists"""
    ensure_auth_data_dir()
    
    # Check if any SuperAdmin already exists
    users = list_users()
    superadmin_exists = any(user["role"] == "SuperAdmin" for user in users)
    
    if superadmin_exists:
        raise HTTPException(status_code=400, detail="SuperAdmin already exists")
    
    # Create SuperAdmin user
    superadmin = create_user(
        username=request.username,
        password=request.password,
        role="SuperAdmin",
        created_by="system"
    )
    
    return {"message": "SuperAdmin created successfully", "username": superadmin["username"]}

@router.post("/logout")
async def logout():
    # JWT tokens are stateless, so logout is handled client-side
    return {"message": "Logout successful"}