## Current Repo Fit
- Backend is FastAPI ([main.py](file:///c:/python%20programs/electron_frs/backend_face/main.py)) with multiple mounted routers/apps (camera management, registration, events, etc.).
- Cameras/collections already persist to JSON under backend_face/data/camera_management ([service.py](file:///c:/python%20programs/electron_frs/backend_face/camera_management/service.py)).
- Frontend is React (tab-based navigation) inside the Electron frontend folder ([App.js](file:///c:/python%20programs/electron_frs/frontend/src/App.js)); no auth, no router guards, no menu system yet.

## Decisions (to match JSON-DB PoC)
- Implement token auth as JWT in the Authorization header (Bearer), stored client-side in localStorage for now.
- Password hashing via passlib+bcrypt (already present in environment).
- User IDs as UUID strings; camera IDs remain existing integers.
- No “eagleai” SuperAdmin backdoor by default (not previously approved). Instead: explicit bootstrap creation.
- Camera assignment is exclusive by default (one camera → one supervisor), with a clear switch point if you later want shared.

## Backend Implementation
### 1) JSON persistence layer
- Add a small storage module (file-based JSON) with atomic writes and a process-local lock.
- Create new data files under backend_face/data/auth:
  - users.json (users)
  - settings.json (global limits + feature flags)
  - audit.json (audit log entries)
  - camera_assignments.json (camera_id → supervisor_id) OR keep assignments embedded in supervisor users (we’ll likely do both: source of truth is camera_assignments for exclusivity; derived assigned_cameras stored on supervisor for fast reads).

### 2) Auth + RBAC
- Add auth router:
  - POST /api/auth/login: validate username/password; optionally validate role selection; issue JWT with expiry; return {token, user, expires_at}.
  - POST /api/auth/logout: for JWT, this is a no-op server-side but returns 200 (optionally add token revocation list later).
- Add auth middleware that:
  - Enforces authentication for /api/* except allowlist: /api/status, /api/auth/login, static paths.
  - Sets request.state.user for downstream use.
- Add helper dependencies:
  - get_current_user
  - ensure_role([...])
  - ensure_menu("cameras"/"events"/etc.) for server-side menu enforcement where applicable.

### 3) User management endpoints
- Implement:
  - GET /api/users/me
  - GET /api/users (SuperAdmin sees all; Admin sees only users created_by them)
  - POST /api/users (SuperAdmin can create Admin/Supervisor; Admin can create Supervisor only)
  - PATCH /api/users/{id} (role/menus/camera_limit/assigned_cameras rules enforced)
- Enforce camera_limit bounds:
  - settings.json provides max values and whether Admin can set camera_limit and/or supervisor menus.
- Bootstrap flow:
  - Add a one-time endpoint (e.g., POST /api/bootstrap/superadmin) allowed only if users.json is empty, OR a CLI script to create the first SuperAdmin; document in README.

### 4) Camera list + assignment endpoints
- Extend camera model to include optional owner_admin_id (backward compatible; existing cameras remain accessible to SuperAdmin/Admin as “legacy/unowned”).
- Add:
  - GET /api/cameras: SuperAdmin returns all; Admin returns owned + legacy; Supervisor returns assigned.
  - POST /api/cameras/assign: Admin/SuperAdmin only; validates supervisor exists; enforces exclusivity; enforces camera_limit; returns updated assigned list or 400 with "exceeds_camera_limit".
- Integrate with existing camera management:
  - Protect camera CRUD endpoints so Supervisors can’t create/update/delete cameras.
  - When Admin creates a camera via existing endpoint, set owner_admin_id to that admin.

### 5) Audit log
- Append audit entries for:
  - CREATE_USER / UPDATE_USER / DELETE_USER (if implemented)
  - ASSIGN_CAMERAS / UNASSIGN_CAMERAS
- Implement GET /api/audit (SuperAdmin only).

## Frontend Implementation
### 1) Auth UI (login)
- Add an IllustratedLogin-style LoginPage component:
  - Username, password, role dropdown (Admin/Supervisor), remember me.
  - Calls POST /api/auth/login.
  - Persists token + user in Zustand + localStorage (if remember me).
  - Shows friendly errors.

### 2) Auth state + API wrapper
- Add a Zustand auth store with:
  - token, user, expiresAt, login(), logout(), hydrateFromStorage().
- Add a fetch wrapper that:
  - Uses existing API_BASE_URL logic.
  - Injects Authorization: Bearer <token>.
  - Handles 401 by logging out.

### 3) Role/menu-driven sidebar
- Replace hard-coded tabs list in App.js with a menu registry:
  - Each menu key maps to {label, icon, component}.
  - Render only items in currentUser.menus.
- Add Logout button.

### 4) Admin console + camera assignment UI
- Add pages/components:
  - AdminConsole: list users (scoped by role/domain), create supervisor/admin per permissions, edit menus + camera_limit.
  - CameraAssignment: select supervisor → select cameras → assign (shows X/Y badge).
- Supervisor view:
  - A simplified SupervisorConsole page that lists assigned cameras and launches existing viewer components.

## Tests (basic, to satisfy acceptance)
- Add backend tests using Python unittest + FastAPI TestClient:
  - Camera assignment enforces camera_limit.
  - Role checks: Supervisor cannot call /api/cameras/assign; Admin cannot create Admin.
  - Exclusivity: camera cannot be assigned to multiple supervisors.

## Migration/Compatibility
- Existing cameras.json/collections.json remain valid.
- owner_admin_id is optional; we don’t rewrite existing files, only set it on new/updated cameras.
- No breaking change to /api/status (used by frontend backend autodetection).

## Deliverables Produced
- Backend: auth middleware + RBAC, user CRUD, camera assign endpoint, audit logs, JSON persistence.
- Frontend: Login page, auth store, menu-driven sidebar, Admin/Supervisor consoles.
- README: how to bootstrap first SuperAdmin + set defaults in settings.json.

If you confirm, I’ll implement backend first (auth + RBAC + camera assignment + tests), then wire frontend login/menu/console screens to the new APIs.