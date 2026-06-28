# AudioMIX
# api/routes/transport.py
#
# Transport control endpoints.
# Receives play/pause/stop/record actions from the
# AudioMIX-Electron Transport.jsx component and
# updates SessionState accordingly.
#
# Endpoints:
#    POST /transport - transport action (play, pause,
#    stop, record)
#    POST /transport/bpm - update BPM
#    GET /transport/status - current transport state
#    only (lightweight poll)

import logging
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from api.bridge import bridge
from api.models import (
    TransportRequest,
    TransportResponse,
    TransportAction,
    SessionStateModel,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transport", tags=["transport"])

# Request Models
class BPMUpdateRequest(BaseModel):
    """
    Updates BPM independently of a transport action.
    """
    bpm: int = Field(..., ge=20, le=300, description="BPM between 20 and 300")

class TransportStatusResponse(BaseModel):
    """
    Lightweight transport status - subset of full SessionState.
    Used for polling w/o pulling the entire session payload.
    """
    is_playing: bool
    is_recording: bool
    playback_position: float
    playhead_bar: float
    bpm: Optional[int]
    time_signature: tuple

# Endpoints
@router.post("", response_model=TransportResponse)
async def transport_action(request: TransportRequest) -> TransportResponse:
    """
    Handles a transport action from the Electron Transport.jsx component.
    Actions:
        play - start playback, clear recording state
        pause - pause playback, retain position
        stop - stop playback, reset position to 0
        record - toggle recording state, starts playback if not playing
    
    If request includes bpm, updates BPM at the same time as the action.
    All connected WebSocket clients receive a session_update push
    immediately after the state change.
    
    Request body:
        { "action": "play" }
        { "action": "stop" }
        { "action": "record", "bpm": 140 }
    
    Returns:
        TransportResponse w/ updated session state
    """
    logger.info(f"POST /transport - action: {request.action}")
    return await bridge.handle_transport(request)

@router.post("/bpm", response_model=SessionStateModel)
async def update_bpm(request: BPMUpdateRequest) -> SessionStateModel:
    """
    Update BPM w/o triggering a transport action.
    Called when the producer clicks the BPM display in Transport.jsx
    and enters a new value. 

    Validated between 20-300 BPM so producer can't accidentally set nonsensical
    BPM values through the UI (e.g., 0 BPM or 999 BPM)
    
    All connected WebSocket clients receive a session_update push
    so the BPM display updates across all surfaces immediately.

    Args:
        request: BPMUpdateRequest w/ new bpm value
    
    Returns:
        Updated SessionStateModel
    """
    logger.info(f"POST /transport/bpm - {request.bpm}")
    bridge._session.bpm = request.bpm
    bridge._session.last_event = f"bpm:{request.bpm}"
    await bridge._notify_clients()
    return bridge.get_session_state()

@router.get("/status", response_model=TransportStatusResponse)
async def get_transport_status() -> TransportStatusResponse:
    """
    Returns lightweight transport status w/o full session payload.
    Used by the Electron Transport.jsx component for lightweight polling
    when the WebSocket connection is unavailable or not yet established.

    Cheaper than GET /session for clients that only need transport state.
    Once the WebSocket is up, it stops polling and switches to the push model.
    
    Returns:
        TransportStatusResponse - is_playing, is_recording, position,
        playhead_bar, bpm, time_signature
    """
    logger.debug("GET /transport/status")
    session = bridge._session
    return TransportStatusResponse(
        is_playing = session.is_playing,
        is_recording = session.is_recording,
        playback_position = session.playback_position,
        playhead_bar = session.playhead_bar,
        bpm = session.bpm,
        time_signature = session.time_signature,
    )