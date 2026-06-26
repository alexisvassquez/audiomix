# AudioMIX
# api/routes/session.py
#
# Session state endpoint
# Exposes current SessionState to the AudioMIX Electron UI
# via REST.
#
# Endpoints:
#    GET /session - full current session state
#    POST /session/project - update project name
#    POST /session/scene - update active scene

import logging
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from api.bridge import bridge
from api.models import SessionStateModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/session", tags=["session"])

# Request Models
class ProjectUpdateRequest(BaseModel):
    """
    Updates the active project name.
    """
    project_name: str

class SceneUpdateRequest(BaseModel):
    """
    Updates the active scne.
    Will be more in effect as HAL is implemented with
    LED integration for live performance engine.
    """
    scene_name: str

# Endpoints
@router.get("", response_model=SessionStateModel)
async def get_session() -> SessionStateModel:
    """
    Return the full current session state.
    Called by the Electron UI on startup and whenever it
    needs to resync with the engine (e.g., after reconnecting
    a lost WebSocket connection).
    
    The Electron TopBar and StatusBar read from this endpoint to
    populate project name, mode, audio telemetry, and Juniper2.0
    status on initial load.
    
    Returns:
        Full SessionStateModel - serialized SessionState dataclass
    """
    logger.debug("GET /session")
    return bridge.get_session_state()

@router.post("/project", response_model=SessionStateModel)
async def update_project(request: ProjectUpdateRequest) -> SessionStateModel:
    """
    Update the active project name.
    Reflect immediately in:
        - TopBar.jsx project display
        - StatusBar.jsx project label
        - All connected WebSocket clients via session_update push
    
    Args:
        request: ProjectUpdateRequest w/ new project_name
    
    Returns:
        Updated SessionStateModel
    """
    logger.info(f"POST /session/project - {request.project_name}")
    bridge._session.project_name = request.project_name
    bridge._session.last_event = f"project:{request.project_name}"
    await bridge._notify_clients()
    return bridge.get_session_state()

@router.post("/scene", response_model=SessionStateModel)
async def update_scene(request: SceneUpdateRequest) -> SessionStateModel:
    """
    Update the active scene name.
    Will be more in effect as HAL is implemented with LED integration 
    for live performance engine.
    Reflected immediately in:
        - Sidebar.jsx active scene highlight
        - StatusBar.jsx scene display
        - All connected WebSocket clients via session_update push
    
    Args:
        request: SceneUpdateRequest w/ newe scene_name
    
    Returns:
        Updated SessionStateModel
    """
    logger.info(f"POST /session/scene - {request.scene_name}")
    bridge._session.scene_name = request.scene_name
    bridge._session.last_event = f"scene:{request.scene_name}"
    await bridge._notify_clients()
    return bridge.get_session_state()