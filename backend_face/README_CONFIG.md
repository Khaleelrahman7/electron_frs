# Backend Configuration Guide

## API URL Configuration

The backend can be configured to work in both local and server environments.

### Default Behavior

- **Default**: `http://192.168.1.209:8005` (for local development)
- **Can be overridden** via environment variable

### Configuration

#### For Local Development (Default)

No configuration needed - backend defaults to `192.168.1.209:8005`:

```bash
cd backend_face
python start_server.py
# Backend runs on http://192.168.1.209:8005
```

#### For Server Deployment

Set the `API_BASE_URL` environment variable before starting:

```bash
# On server (192.168.1.209)
export API_BASE_URL=http://192.168.1.209:8005
cd /home/eagle/FRS/backend_face
python start_server.py
```

Or add to your startup script:

```bash
#!/bin/bash
export API_BASE_URL=http://192.168.1.209:8005
cd /home/eagle/FRS/backend_face
source /home/eagle/face_match/pyqt_env/bin/activate
python start_server.py
```

### What This Affects

The `API_BASE_URL` environment variable is used by:
- `event/event_api.py` - For constructing image URLs sent to frontend
- Image URLs in API responses will use this base URL

### Port Configuration

The server port is configured in:
- `start_server.py` - Default port: 8005
- `main.py` - Also defaults to 8005

To change port, edit `start_server.py`:
```python
uvicorn.run(app, host="0.0.0.0", port=8005)  # Change 8005 to desired port
```

### Network Configuration

For server deployment:
- Server binds to `0.0.0.0` (all interfaces) - accessible from network
- Ensure firewall allows port 8005
- CORS is configured to allow all origins (`allow_origins=["*"]`)

### Verification

Check which URL is being used:
1. Check server logs on startup
2. Check API responses - image URLs will show the configured base URL
3. Test: `curl http://192.168.1.209:8005/api/status` (local) or `curl http://192.168.1.209:8005/api/status` (server)

