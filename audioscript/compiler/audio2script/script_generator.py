# AudioMIX
# audioscript/compiler/audio2script/script_generator.py

from __future__ import annotations

import os
from io import StringIO
from typing import Dict, List

from audioscript.compiler.audio2script.script_ir import ShowIR, Section, Event

"""
AudioScript (AS) code generator.

Takes a ShowIR (intermediate representation of an AI auto-generated show)
and emits AudioScript (AS) source code using the block-based, C-like syntax:

track "name" {
    bpm 128

    section "intro" from 0.0 to 8.0 {
        at 0.0 {
            leds.ambient(front_strip, intensity: 0.3);
        }
    }
}
"""

# Derive a reasonable track name from an audio file path
# e.g., 'audio/samples/cvltiv8r_clean.wav' -> 'cvltiv8r_clean'
def _track_name_from_path(audio_path: str) -> str:
    base = os.path.basename(audio_path)
    name, _ext = os.path.splitext(base)
    return name

# Group events by section label, based on time
# time-contained-in-[start,end] rule
def _group_events_by_section(sections: List[Section], events: List[Event]) -> Dict[str, List[Event]]:
    grouped: Dict[str, List[Event]] = {s.label: [] for s in sections}
    for e in events:
        for s in sections:
            if s.start <= e.time < s.end:
                grouped[s.label].append(e)
                break
    # Ensure events within each section are sorted by time
    for label in grouped:
        grouped[label].sort(key=lambda ev: ev.time)
    return grouped

# Map an Event to a single AudioScript (AS) statement line.
# Event types mapping will be extended as further versions are released.
def _emit_event_line(event: Event, indent: str = " " * 8) -> str:
    t = event.type
    p = event.params

    # DEFAULTS so missing params don't explode
    raw_intensity = float(p.get("intensity", 0.5))
    intensity = float(raw_intensity) if isinstance(raw_intensity, (int, float, str)) else 0.5

    raw_duration = float(p.get("duration", 4.0))
    duration = float(raw_duration) if isinstance(raw_duration, (int, float, str)) else 4.0

    raw_strobe= float(p.get("strobe_intensity", 1.0))
    strobe_intensity = float(raw_strobe) if isinstance(raw_strobe, (int, float, str)) else 1.0

    # semantics (more refinement needed)
    if t == "ambient_fade_in":
        return f'{indent}leds.ambient(front_strip, intensity: {intensity:.2f});'

    if t == "ambient_fade_out":
        return f'{indent}leds.fade_all(duration: {duration:.2f});'

    if t == "build_rise":
        return f'{indent}leds.rise_all(duration: {duration:.2f});'

    if t == "drop_flash":
        return f'{indent}leds.flash_all(strobe_intensity: {strobe_intensity:.2f});'

    # Placeholder for future events
    if t == "energy_peak":
        energy = float(p.get("energy", 0.8))
        return f'{indent}leds.wave(ceiling, energy: {energy:.2f});'

    if t == "kick_hit":
        return f'{indent}leds.pulse(front_strip, decay: 0.15);'

    # Fallback: comment out unknown events for now
    return f'{indent}//TODO: unhandled event type="{t}" params={p}'

# Generate AudioScript (AS) source code for the given show IR
# Returns a string containing the full AudioScript (AS) program
def generate_audioscript(show: ShowIR) -> str:
    buf = StringIO()

    track_name = show.metadata.get("title") or _track_name_from_path(show.audio_path)
    bpm_int = int(round(show.bpm))

    buf.write(f'track "{track_name}" {{\n\n')
    buf.write(f"    bpm {bpm_int}\n\n")

    # Group events by section
    events_by_section = _group_events_by_section(show.sections, show.sorted_events())

    # Emit each section block
    for section in show.sections:
        label = section.label
        start = section.start
        end = section.end

        buf.write(f'    section "{label}" from {start:.3f} to {end:.3f} {{\n')

        # Emit each event in this section as an `at` block
        section_events = events_by_section.get(label, [])
        for ev in section_events:
            buf.write(f'        at {ev.time:.3f} {{\n')
            buf.write(_emit_event_line(ev, indent=" " * 12) + "\n")
            buf.write("        }\n")

        buf.write("    }\n\n")

    buf.write("}\n")
    return buf.getvalue()
