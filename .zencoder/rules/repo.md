---
description: Repository Information Overview
alwaysApply: true
---

# Repository Information Overview

## Repository Summary
A face recognition system with an Electron-based desktop frontend for user interface and a Python backend for face detection, recognition, and camera management.

## Repository Structure
The repository contains three main directories: frontend/ for the Electron application, backend_face/ for the Python server, and recordings/ for shared video recordings.

### Main Repository Components
- **Frontend**: Electron desktop application built with React for gallery view, face events, and real-time backend connectivity.
- **Backend**: Python server handling face recognition, camera streaming, and API endpoints.
- **Recordings**: Shared directory for storing video recordings.

## Projects

### Frontend (Electron App)
**Configuration File**: frontend/package.json

#### Language & Runtime
**Language**: JavaScript (React)
**Version**: Node.js v14+, Electron ^27.0.0, React ^18.2.0
**Build System**: npm
**Package Manager**: npm

#### Dependencies
**Main Dependencies**:
- axios ^1.6.0
- date-fns ^2.30.0
- electron ^27.0.0
- form-data ^4.0.0
- lucide-react ^0.263.1
- react ^18.2.0
**Development Dependencies**:
- concurrently
- wait-on
- react-scripts
- electron-builder

#### Build & Installation
```bash
npm install
npm run build
npm run electron-pack
```

### Backend (Python Server)
**Configuration File**: backend_face/README_CONFIG.md

#### Language & Runtime
**Language**: Python
**Version**: Not specified (uses various package versions)
**Build System**: None
**Package Manager**: pip

#### Dependencies
**Main Dependencies** (from server_packages_list.txt):
- fastapi (implied from context)
- opencv-python
- torch
- ultralytics
- aiofiles
- alembic
- sqlalchemy
- uvicorn
- Additional ML/AI packages: accelerate, transformers, etc.

#### Build & Installation
```bash
cd backend_face
pip install [packages from server_packages_list.txt]
python start_server.py
```