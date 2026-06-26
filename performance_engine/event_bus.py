# audiomix
# AudioMIX
# performance_engine/event_bus.py

# AudioMIX Event Bus
"""
A lightweight publish/subscribe message
bus that decouples AudioMIX's internal
components from one another.
Any module can emit a named event w/o knowing who is listening.
Modules can also subscribe to a named event w/o knowing who emits it.

This keeps the AI layer, DSP bridge, performance engine, and AS runtime all loosely coupled.
Communication bridge - communicate through events rather than direct function calls/imports.

The singleton `bus` instance at the bottom of script is the single shared bus for all of AudioMIX.
Always import that instance directly rather than instantiating a new EventBus
* separate instances do no share subscribers.
"""

class EventBus:
    def __init__(self):
        self._subscribers = {}

    def on(self, event_name, handler):
        # Register a handler function for the given event name
        self._subscribers.setdefault(event_name, []).append(handler)

    def emit(self, event_name, payload=None):
        # Emit an event
        # calls all registered handlers w/ the payload
        for handler in self._subscribers.get(event_name, []):
            handler(payload)

# single shared instance for all of AudioMIX
# import directly:
#  from performance_engine.event_bus import bus
bus = EventBus()
