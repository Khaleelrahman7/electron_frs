from typing import Optional, List, Dict, Any
from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .security import verify_token
from .users import get_user
from datetime import datetime, timezone
from .storage import get_tokens

security = HTTPBearer()

PUBLIC_PATHS = {
    "/api/auth/login",
    "/api/auth/bootstrap/superadmin",
    "/api/status",
    "/"
}

PUBLIC_PATH_PREFIXES = [
    "/api/gallery/image",
    "/api/captured/image"
]

ROLE_HIERARCHY = {
    "SuperAdmin": ["Admin", "Supervisor"],
    "Admin": ["Supervisor"],
    "Supervisor": []
}

def get_current_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    token_data = verify_token(token)
    if not token_data:
        return None
    
    username = token_data.get("username")
    if not username:
        return None
    
    user = get_user(username)
    if not user or not user.get("is_active", True):
        return None
    
    return user

def is_admin_license_valid(user: Dict[str, Any]) -> bool:
    if user.get("role") != "Admin":
        return True
    end_str = user.get("license_end_date")
    if not end_str:
        # No license specified -> treat as valid (unlimited) for backward compatibility
        return True
    try:
        end_dt = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    return end_dt >= now

def check_permission(current_user: Dict[str, Any], required_role: str) -> bool:
    user_role = current_user.get("role")
    if not user_role:
        return False
    
    if user_role == required_role:
        return True
    
    # Check if user can manage users of the required role
    if user_role in ROLE_HIERARCHY and required_role in ROLE_HIERARCHY[user_role]:
        return True
    
    return False

def check_path_permission(current_user: Dict[str, Any], path: str, method: str) -> bool:
    user_role = current_user.get("role")
    if not user_role:
        return False
    
    # Allow OPTIONS requests for CORS preflight
    if method == "OPTIONS":
        return True
    
    # SuperAdmin can access everything
    if user_role == "SuperAdmin":
        return True
    
    # Admin restrictions
    if user_role == "Admin":
        # Admins cannot access SuperAdmin-only endpoints
        if path.startswith("/api/users/") and ("superadmin" in path.lower() or path.endswith("/logs")):
            return False
        return True
    
    # Supervisor restrictions
    if user_role == "Supervisor":
        # Supervisors can access dashboard, cameras, analytics, registration, collections, and events
        allowed_paths = [
            "/api/dashboard", 
            "/api/cameras", 
            "/api/auth/me",
            "/api/analytics",
            "/api/registration",
            "/api/collections",
            "/api/events"
        ]
        return any(path.startswith(allowed) for allowed in allowed_paths)
    
    return False

class RBACMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        
        # Allow public paths
        if path in PUBLIC_PATHS or any(path.startswith(prefix) for prefix in PUBLIC_PATH_PREFIXES):
            await self.app(scope, receive, send)
            return
        
        # Allow OPTIONS requests for CORS preflight
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        
        # Check for authorization header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        
        if not auth_header.startswith("Bearer "):
            await self.send_unauthorized(send)
            return
        
        token = auth_header[7:]  # Remove "Bearer "
        current_user = get_current_user_from_token(token)
        
        if not current_user:
            await self.send_unauthorized(send)
            return
        
        # Check token is active (not revoked)
        tokens = get_tokens()
        if token not in tokens:
            await self.send_unauthorized(send)
            return
        
        # Enforce Admin license on all protected endpoints
        if current_user.get("role") == "Admin" and not is_admin_license_valid(current_user):
            await self.send_forbidden(send, message=b'{"detail": "License expired. Contact SuperAdmin."}')
            return
        
        # Check path permissions
        if not check_path_permission(current_user, path, method):
            await self.send_forbidden(send)
            return
        
        # Add user info to scope for use in endpoints
        scope["user"] = current_user
        await self.app(scope, receive, send)
    
    async def send_unauthorized(self, send):
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"detail": "Not authenticated"}',
        })
    
    async def send_forbidden(self, send, message: bytes = b'{"detail": "Not enough permissions"}'):
        await send({
            "type": "http.response.start",
            "status": 403,
            "headers": [[b"content-type", b"application/json"]],
        })
        await send({
            "type": "http.response.body",
            "body": message,
        })
