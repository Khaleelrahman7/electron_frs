"""
WebRTC streaming routes
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from .webrtc_service import get_webrtc_manager, WebRTCStreamManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["webrtc"])

@router.websocket("/webrtc/{camera_id}")
async def websocket_webrtc_endpoint(
    websocket: WebSocket,
    camera_id: int,
    webrtc_manager: WebRTCStreamManager = Depends(get_webrtc_manager)
):
    """WebSocket endpoint for WebRTC signaling"""
    try:
        await webrtc_manager.connect(websocket, str(camera_id))
    except WebSocketDisconnect:
        logger.info(f"WebRTC WebSocket disconnected for camera {camera_id}")
    except Exception as e:
        logger.error(f"WebRTC WebSocket error for camera {camera_id}: {e}")
