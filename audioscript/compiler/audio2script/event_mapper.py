# AudioMIX
# audioscript/compiler/audio2script/event_mapper.py


from typing import List
from audioscript.compiler.audio2script.script_ir import ShowIR, FeatureFrame, Section, Event

"""
Event Mapper v1

Music-aware Semantic Mapping
Consumes:
    - FeatureFrames (time, energy, onset_strength, bass/mids/highs, centroid)
    - Sections (intro/build/drop/outro)
    - BPM

Produces a ShowIR populated w/ expressive lighting events
"""

# Thresholds (tunable)
KICK_THRESHOLD = 0.65          # onset_strength threshold for transient/kick hits
BRIGHTNESS_THRESHOLD = 0.70    # spectral centroid above this = bright flash
ENERGY_PEAK_THRESHOLD = 0.75   # rms/energy threshold for hype moments
MIN_EVENT_SPACING = 0.10       # to avoid spamming events

# Generates ShowIR from medium-complex analysis
def map_features_to_events(
    audio_path: str,
    frames: List[FeatureFrame],
    sections: List[Section],
    bpm: float,
) -> ShowIR:
    show = ShowIR(
        audio_path=audio_path,
        bpm=bpm,
        sections=sections,
        events=[],
        profile_name="medium-reactive-v1"
    )

    # Keep track of last events to prevent spam
    last_kick_time = -999
    last_brightness_time = -999
    last_energy_time = -999

    # Section-level semantic events
    for sec in sections:
        if sec.label == "intro":
            show.add_event(Event(
                time=sec.start,
                type="ambient_fade_in",
                params={"intensity": 0.25}
            ))

        elif sec.label == "build":
            show.add_event(Event(
                time=sec.start,
                type="build_rise",
                params={"duration": sec.duration()}
            ))

        elif sec.label == "drop":
            show.add_event(Event(
                time=sec.start,
                type="drop_impact",
                params={"intensity": 1.0}
            ))

        elif sec.label == "outro":
            show.add_event(Event(
                time=sec.start,
                type="ambient_fade_out",
                params={"duration": sec.duration()}
            ))

        # for unknown sections, fallback to ambient fade
        else:
            show.add_event(Event(
                time=sec.start,
                type="ambient_fade_in",
                params={"intensity": 0.25}
            ))

    # Frame-level reactive lighting
    for f in frames:
        # Kick / Transient (based on onset strength)
        if f.onset_strength > KICK_THRESHOLD and (f.time - last_kick_time):
            show.add_event(Event(
                time=f.time,
                type="kick_hit",
                params={
                    "decay": 0.12,
                    "intensity": min(1.0, f.onset_strength + 0.2)
                }
            ))
            last_kick_time = f.time

    # Brightness Flash (spectral centroid)
    if f.highs_level > BRIGHTNESS_THRESHOLD and (f.time - last_brightness_time) > MIN_EVENT_SPACING:
        show.add_event(Event(
            time=f.time,
            type="brightness_flash",
            params={
                "strength": min(1.0, f.highs_level + 0.2)
            }
        ))
        last_brightness_time = f.time

    # Energy Peak (global hype moments)
    if f.energy > ENERGY_PEAK_THRESHOLD and (f.time - last_energy_time) > MIN_EVENT_SPACING:
        show.add_event(Event(
            time=f.time,
            type="energy_wave",
            params={
                "amplitude": f.energy,
                "color_shift": f.mids_level
            }
        ))
        last_energy_time = f.time

    return show
