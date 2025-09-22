import asyncio
import json
import logging
from typing import Optional

from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..webrtc_stream import RTSPVideoStreamTrack, create_webrtc_stream, stop_webrtc_stream

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

class WebRTCOffer(BaseModel):
    rtspUrl: str
    offer: dict

@router.post("/api/webrtc/connect")
async def connect_webrtc(offer_data: WebRTCOffer):
    try:
        # Create a new WebRTC stream
        stream_info = create_webrtc_stream(offer_data.rtspUrl, "direct")
        if not stream_info:
            raise HTTPException(status_code=500, message="Failed to create WebRTC stream")

        # Create peer connection
        pc = RTCPeerConnection()
        
        # Add video track to peer connection
        pc.addTrack(stream_info['video_track'])

        # Set the remote description (client's offer)
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=offer_data.offer['sdp'], type=offer_data.offer['type'])
        )

        # Create and set local description (answer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        return {
            "answer": {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type
            }
        }

    except Exception as e:
        logger.error(f"Error in connect_webrtc: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/webrtc/disconnect/{stream_id}")
async def disconnect_webrtc(stream_id: str):
    try:
        stop_webrtc_stream(stream_id)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Error in disconnect_webrtc: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))