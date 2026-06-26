# audiomix
# AudioMIX
# api/models.py
#
# Pydantic models for the FastAPI bridge layer.
# These mirror the SessionState dataclasses located in
# performance_engine/session_state.py.
# Review file for reference.
# Shaped for HTTP/WebSocket serialization, validated on
# every message going in and out of the API layer.
# Rule: if SessionState gains a field, a corresponding
# Pydantic model field would be added here to keep the
# contract explicit and typed.

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum

# Enums
class AudioScriptBranch(str, Enum):
    IR = "ir"
    LIVE = "live"

class HALDeviceType(str, Enum):
    LED = "led"
    MIDI = "midi"
    OSC = "osc"
    DMX = "dmx"
    AUDIO = "audio"
    UNKNOWN = "unknown"

class HALDeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    IDLE = "idle"

class TransportAction(str, Enum):
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"
    RECORD = "record"

# HAL Device
class HALDeviceModel(BaseModel):
    """
    Mirrors HALDevice dataclass in 
    performance_engine/session_state.py
    Surfaced in the Electron sidebar HAL devices panel.
    HALDevice is in development.
    """
    name: str
    status: HALDeviceStatus = HALDeviceStatus.OFFLINE
    detail: str = ""
    device_type: HALDeviceType = HALDeviceType.UNKNOWN

# Clip Layer
class ClipLayerModel(BaseModel):
    """
    Mirrors ClipLayer dataclass in session_state.py
    One audio layer inside a clip container.
    """
    id: str
    name: str
    source_file: str
    gain: float = Field(default=1.0, ge=0.0, le=1.0)
    freq_profile: List[float] = Field(
        default_factory=lambda: [0.0] * 7,
        description="7-band energy profile: SUB, BASS, LO MID, MID, HI MID, PRESENCE, AIR"
    )

# Clip State
class ClipStateModel(BaseModel):
    """
    Mirrors ClipState dataclass. Read comments above.
    A clip container holding one or more audio layers.
    """
    id: str
    track_id: int
    name: str
    start_bar: int
    length_bars: int
    layers: List[ClipLayerModel] = Field(default_factory=list)
    is_dragging: bool = False

# Session State
class SessionStateModel(BaseModel):
    """
    Full session state - serialized and pushed to Electron
    GUI via WebSocket on every meaningful state change.
    Mirrors SessionState dataclass.
    Some features are in active development. Noted.
    
    GUI surface mapping:
        Transport fields - useTransport hook, Transport.jsx
        Project fields - TopBar.jsx, StatusBar.jsx
        Musical context - Transport.jsx BPM, Juniper2.0
        AudioScript field - AS Shell panel (in dev), Sidebar.jsx
        Mix context - Right panel knobs, EQ
        Telemetry fields - StatusBar.jsx real-time stats
        HAL fields - Sidebar HAL panel. PERFORM mode (dev)
    """
    # Transport
    is_playing: bool = False
    is_recording: bool = False
    playback_position: float = 0.0
    playhead_bar: float = 0.0

    # Project
    project_name: Optional[str] = None
    scene_name: Optional[str] = None
    current_track: Optional[str] = None

    # Musical context
    bpm: Optional[int] = None
    key: Optional[str] = None
    mood: str = "neutral"
    time_signature: Tuple[int, int] = (4, 4)

    # AudioScript
    active_script: Optional[str] = None
    audioscript_branch: AudioScriptBranch = AudioScriptBranch.IR
    last_as_command: Optional[str] = None
    last_as_result: Optional[str] = None

    # Mix context
    eq_profile: Optional[str] = None
    gain: float = 1.0
    pan: int = 0
    reverb_mix: float = 0.0
    compressor_ratio: float = 1.0
    delay_ms: float = 0.0

    # Audio telemetry
    # fed from PortAudio stream stats
    sample_rate: int = 48000
    buffer_size: int = 256
    latency_ms: float = 0.0
    cpu_percent: float = 0.0

    # Clips
    active_clips: Dict[str, ClipStateModel] = Field(default_factory=dict)

    # HAL devices
    hal_devices: Dict[str, HALDeviceModel] = Field(default_factory=dict)

    # Lighting
    active_zones: Dict[str, Any] = Field(default_factory=dict)

    # Introspection
    last_event: Optional[str] = None
    last_error: Optional[str] = None

# Request Models
class ShellCommandRequest(BaseModel):
    """
    Sent from Electron AS Shell panel to POST /command.
    A single AudioScript command string.
    Logic. AS Shell panel is in active development.
    """
    command: str = Field(
        ...,
        min_length=1,
        description="AudioScript command to evaluate"
    )
    branch: AudioScriptBranch = AudioScriptBranch.LIVE

class ShellCommandResponse(BaseModel):
    """
    Returned from POST /command or pushed over WS /shell.
    Contains the evaluation result and updated session state.
    """
    success: bool
    command: str
    result: Optional[str] = None
    error: Optional[str] = None
    session: Optional[SessionStateModel] = None

class TransportRequest(BaseModel):
    """
    Sent from Electron Transport.jsx to POST /transport
    Controls playback state.
    """
    action: TransportAction
    # included when changing BPM
    bpm: Optional[int] = None

class TransportResponse(BaseModel):
    """
    Returned from POST /transport
    """
    success: bool
    action: TransportAction
    session: Optional[SessionStateModel] = None

# WebSocket Message Envelope
class WSMessageType(str, Enum):
    # full state push
    SESSION_UPDATE = "session_update"
    # command result
    SHELL_OUTPUT = "shell_output"
    # command from client
    SHELL_INPUT = "shell_input"
    # error notification
    ERROR = "error"
    # receiving connection
    PING = "ping"
    PONG = "pong"

class WSMessage(BaseModel):
    """
    Envelope for all WebSocket messages in both directions.
    Every message (client to server + server to client)
    is wrapped in this envelope so the Electron renderer
    can dispatch on `type` without guessing the shape.
    """
    type: WSMessageType
    payload: Optional[Dict[str, Any]] = None


