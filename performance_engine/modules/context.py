# audiomix
# AudioMIX
# performance_engine/modules/context.py

"""
Central runtime context for AudioMIX

This module owns:
- command registry
- session state
- event bus

All runtime modules import shared state from here.
"""

# Command Registry
command_registry = {}

# Runtime State
from performance_engine.session_state import SessionState
from performance_engine.event_bus import EventBus

session = SessionState()
events = EventBus()

# Lifecycle Helpers
"""
Reset the AudioMIX runtime to a clean session state.
Does not tear down hardware or reload modules.
"""
from performance_engine.modules.shared import say

def reset_context():
    session.__dict__.update(SessionState().__dict__)
    session.last_event = "context_reset"

    say("Context reset: new session ready")
    events.emit("context_reset")
