# audiomix
# AudioMIX
# performance_engine/modules/reset.py

from performance_engine.modules.context import reset_context
from performance_engine.modules.shared import say

"""
AudioScript (AS) command: reset()
Clears the current runtime session and returns AudioMIX to a clean
state
"""

def reset():
    reset_context()
    say("AudioMIX reset complete", "♻️")

def register():
    return {
        "reset": reset
    }
