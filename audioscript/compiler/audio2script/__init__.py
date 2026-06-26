# audiomix
# AudioMIX
# audio/ai/audio2script/__init__.py

"""
audio2script: Convert audio into an intermediate 'ShowIR' representation
that can be compiled into AudioScript(AS) for live performance.

The AudioScript package will eventually contain:
- analyzer.py          # audio -> FeatureFrames + Sections + BPM
- event_mapper.py      # features -> semantic Events (ShowIR)
- script_generator.py  # ShowIR -> AudioScript source code
- profiles.py          # different lighting/behavior profiles per show type

For now, I am only exposing the IR data structures
"""

from audio.ai.compiler.audio2script.script_ir import FeatureFrame, Section, Event, ShowIR

__all__ = [
    "FeatureFrame",
    "Section",
    "Event",
    "ShowIR",
]
