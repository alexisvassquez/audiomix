# audiomix
# AudioMIX
# audioscript/compiler/audio2script/script_ir.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal

# Low-level analysis frame

# A single point-in-time snapshot of audio feats
# Dense, continuous timeline from the analyzer

@dataclass
class FeatureFrame:
    """
    time:           Timestamp in seconds (relative to start of audio)
    bpm:            Local temp est at this frame (approx)
    energy:         Overall loudness/energy, normalized 0..1..
    bass_level:     Low freq content (0..1)
    mids_level:     Mid freq content (0..1)
    highs_level:    High freq content (0..1)
    onset_strength: Per-frame onset value (transient strength), normalized 0..1
    section_label:  Optional estimation ("guess") of which section this frame belongs to
                    (e.g., "intro", "build", "drop", "verse", "chorus")
    """
    time: float
    bpm: float
    energy: float
    bass_level: float
    mids_level: float
    highs_level: float
    onset_strength: float
    section_label: Optional[str] = None

# Coarse song structure
# A course structural region of the track
# Start/end are in seconds
@dataclass
class Section:
    """
    - intro
    - verse
    - build
    - drop
    - breakdown
    - outro
    """
    start: float
    end: float
    label: str

    def duration(self) -> float:
        return self.end - self.start

# Event primitives
# more to be added as project develops
EventType = Literal[
    "ambient_fade_in",
    "ambient_fade_out",
    "build_rise",
    "drop_flash",
    "energy_peak",
    "energy_lull",
    "kick_hit",
    "snare_hit",
    "hi_hat_tick",
    "sweep",
    "strobe_burst",
]

# A discrete semantic event that will be turned into AudioScript(AS)
@dataclass
class Event:
    """
    time:    Timestamp in seconds (absolute, from start of track)
    type:    Type of event (semantic label)
    params:  Arbitrary numeric/string parameters (intensity, duration, color_key, etc)
    """
    time: float
    type: EventType
    params: Dict[str, float | str] = field(default_factory=dict)

# Top-level intermediate representation (IR): "the show"
# ShowIR is the top-level IR for an AI auto-generated show
@dataclass
class ShowIR:
    """
    audio_path:    Path to the source audio file used for analysis
    bpm:           Global or dominant BPM for the track
    sections:      Coarse structural breakdown into labeled segments
    events:        Time-ordered semantic events
    profile_name:  Name of the 'lighting profile' used to generate these events
                   (e.g., 'festival', 'ambient', 'hyperpop', 'rock')
    metadata:      Optional free-form metadata (track title, artist, key, etc)
    """
    audio_path: str
    bpm: float
    sections: List[Section] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    profile_name: str = "default"
    metadata: Dict[str, str] = field(default_factory=dict)

    # Return events sorted by time (stable)
    def sorted_events(self) -> List[Event]:
        return sorted(self.events, key=lambda e: e.time)

    # Convenience helper to add an event
    def add_event(self, event: Event) -> None:
        self.events.append(event)

    # Convenience helper to add a section
    def add_section(self, section: Section) -> None:
        self.sections.append(section)

    # Return the first section that contains time t or None if not found
    def find_section_for_time(self, t: float) -> Optional[Section]:
        for sec in self.sections:
            if sec.start <= t < sec.end:
                return sec
        return None
