# AudioMIX
# performance_engine/session_state.py

# SessionState is a central data structure that holds the current state of the performance session.
# It is read by the FastAPI bridge and serialized to the Eletron UP via WebSocket
# Every field has a corresponding UI surface in the AudioMIX Electron UI renderer

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple, List

@dataclass
class ClipLayer:
    """
    A single audio layer inside a clip container.
    Clips are containers - each clip can hold multiple
    layers that blend together to form the final sound.
    Mirrors the layer data model in 
    `audiomix-electron/design/audiomix-layers.jsx`
    """
    id: str
    # display name
    name: str
    # audio file path
    source_file: str
    # blend ratio 0.0 - 1.0
    gain: float = 1.0
    # 7-band energy profile [SUB, BASS, LO MID, MID, HI MID, PRESENCE, AIR]
    # used by freq view and clash detection in the GUI
    freq_profile: List[float] = field(default_factory=lambda: [0.0] * 7)

@dataclass
class ClipState:
    """
    A clip container in the arrangement view.
    Each clip can contain multiple layers that blend together.
    Mirrors the clip data model in `audiomix-electron/design/audiomix-layers.jsx`
    """
    id: str
    track_id: int
    name: str
    # bar position in arrangement view
    start_bar: int
    # clip length in bars
    length_bars: int
    layers: List[ClipLayer] = field(default_factory=list)
    # drag state for GUI sync
    is_dragging: bool = False

@dataclass
class HALDevice:
    """
    A connected hardware device (MIDI controller, audio interface, etc.) in the HAL layer.
    HAL covers: LED arrays, DMX lighting rigs, MIDI controllers, OSC devices, and connected stage machinery."""
    name: str
    # "online", "offline", "idle"
    status: str = "offline"
    # human-readable status detail
    detail: str = ""
    # "led", "midi", "dmx", "osc", "audio"
    device_type: str = "unknown"

@dataclass
class SessionState:
    """
    Single source of truth for AudioMIX engine state.
    
    This dataclass is serialized and sent to the Electron UI
    via the FastAPI/WebSocket bridge.
    Every field corresponds to a UI surface in the AudioMIX Electron renderer.
    
    Field groups:
     - Transport (playback) state (useTransport hook, Transport.jsx)
     - Project (TopBar.jsx, StatusBar.jsx)
     - Musical context (BPM, key, mood) (Juniper2.0, Transport.jsx)
     - AudioScript (AS Shell panel, Sidebar.jsx)
     - Mix context (EQ, gain, pan) (Right panel knobs)
     - Audio telemetry (StatusBar.jsx) (real-time stats)
     - Layering system (Arrangement, clip layer model)
     - HAL devices (Sidebar HAL panel, PERFORM mode)
     - Lighting state (LED integration, PERFORM mode)
     - Debug/introspection (for development, not exposed in UI, last event tracking)
    """

    # Transport
    # useTransport hook, Transport.jsx
    is_playing: bool = False
    is_recording: bool = False
    playback_position: float = 0.0    # seconds
    # bar position for GUI playhead
    playhead_bar: float = 0.0

    # Project Identity
    # TopBar.jsx project name, StatusBar.jsx project details
    # GUI expects these to populate the project display and status bar
    project_name: Optional[str] = None
    scene_name: Optional[str] = None
    current_track: Optional[str] = None

    # Musical Context
    # Transport.jsx BPM display, Juniper2.0 context
    bpm: Optional[int] = None
    key: Optional[str] = None
    mood: str = "neutral"
    time_signature: Tuple[int, int] = (4, 4)

    # AudioScript Context
    # AS Shell panel, Sidebar.jsx branch switcher
    # Tracks which script is running and which branch is active for UI display
    active_script: Optional[str] = None
    # "ir", "live"
    audioscript_branch: str = "ir"
    last_as_command: Optional[str] = None
    last_as_result: Optional[str] = None

    # Mix Context
    # Right panel knobs for EQ, gain, pan
    # TODO: wire to DSP chain parameter updates via
    #  CompressorModule, EqModule, GainModule in `audio/dsp/modules/`
    eq_profile: Optional[str] = None
    gain: float = 1.0
    # -100 (L) -> 0 (center) -> +100 (R)
    pan: int = 0
    # 0.0 - 1.0 wet/dry
    reverb_mix: float = 0.0
    # 1:1 - 20:1 compression ratio
    compressor_ratio: float = 1.0
    delay_ms: float = 0.0

    # Audio Telemetry
    # StatusBar.jsx real-time stats display
    # TODO: feed from PortAudio stream stats and sys:get-stats IPC handler
    sample_rate: int = 48000
    buffer_size: int = 256
    latency_ms: float = 0.0
    cpu_percent: float = 0.0

    # Layering System
    # Arrangement view clip layer data model, frequency view, clash detection
    # Mirrors the clip/layer model in `audiomix-electron/design/audiomix-layers.jsx`
    # TODO: populate from arrangement data when clip system is implemented
    active_clips: Dict[str, ClipState] = field(default_factory=dict)

    # HAL Devices
    # Sidebar HAL panel device list, PERFORM mode device status, hardware control surface
    # HAL covers: LED arrays, DMX lighting rigs, MIDI
    # controllers, OSC devices, and connected stage machinery
    # TODO: populate from hardware/led_controller.py and HAL device registry (in development)
    hal_devices: Dict[str, HALDevice] = field(default_factory=dict)

    # Lighting / Stage State
    # LED integration, PERFORM mode stage state display,
    # LED zones, hardware/led_controller.py
    active_zones: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Debug / Introspection
    last_event: Optional[str] = None
    last_error: Optional[str] = None

def make_default_session(project_name: str = "untitled") -> SessionState:
    """
    Factory function for a clean session with sensible defaults.
    Called when AudioMIX starts or a new project is created.
    
    Args:
        project_name: Optional name for the new project, defaults to "untitled". Displayed in TopBar and StatusBar.
    
    Returns:
        A SessionState instance with default values and the specified project name.
    """
    return SessionState(
        project_name=project_name,
        bpm=120,
        key="C",
        mood="neutral",
        time_signature=(4, 4),
        audioscript_branch="ir",
        sample_rate=48000,
        buffer_size=256,
    )

