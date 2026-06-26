# AudioMIX
# performance_engine/modules/midi_bridge.py

import threading, time, json, queue, re, os
from typing import Dict, Any, Optional, List, Callable
from performance_engine.utils.shell_output import say
from performance_engine.modules.context import command_registry
from audio.midi import midi_live_listener as live
from audio.midi import pretty_midi_parser as pmp
from audio.midi import midi_tag_classifier as tagclf
from audio.midi import tag_to_settings as t2s

# MIDI runtime state (explicit defaults)
_midi_in = None
_midi_out = None
_midi_enabled = False
_last_event_sig = None

# Events
_EVENT_Q: "queue.Queue[dict]" = queue.Queue(maxsize=4096)
_listener_thread: Optional[threading.Thread] = None
_stop_flag = threading.Event()
_current_port: Optional[str] = None
_mappings: List[Dict[str, Any]] = []
_last_tags: List[str] = []

def _enqueue(ev: dict):
    try:
        _EVENT_Q.put_nowait(ev)
    except queue.Full:
        pass

# Shim: expect live listener can take a callback per event
def _listener(port_name: str):
    global _current_port
    _current_port = port_name
    say(f"[MIDI] opening '{port_name}'")
    try:
        live.listen(port_name=port_name, on_event=_enqueue, stop_event=_stop_flag)
    except Exception as e:
        say(f"[MIDI] listener error: {e}", "❌")
    finally:
        say("[MIDI] listener stopped", "🛑")

# Command implementations
def midi_ports():
    ports = live.list_input_ports()
    if not ports:
        say("No MIDI inputs found.", "⚠️")
    else:
        say("Available MIDI inputs:")
        for i, p in enumerate(ports):
            say(f" [{i}] {p}")

def midi_listen(port=None):
    global _midi_in, _midi_enabled

    _midi_in = open_midi_port(port)
    _midi_enabled = True

def midi_stop():
    global _midi_in, _midi_enabled

    _midi_in = None
    _midi_enabled = False

def midi_map_load(path: str = "audio/midi/midi_map.json"):
    if not os.path.exists(path):
        say(f"Mapping file not found: {path}", "⚠️")
        return
    try:
        with open(path, "r") as f:
            data = json.load(f)
        _mappings.clear()
        for rule in data.get("rules", []):
            pat = rule.get("match", "")
            action = rule.get("action", "")
            quant = rule.get("quantize", "off")
            compiled = re.compile("^" + pat.replace("*", ".*") + "$")
            _mappings.append({"re": compiled, "action": action, "quant": quant})
        say(f"Loaded {_len(_mappings)} MIDI mapping rule(s) from {path}", "🎼")
    except Exception as e:
        say(f"Failed to load midi_map: {e}", "❌")

def _fire_action(action: str, ev: dict):
    """
    Allows actions like:
        - play("<file_name>.wav")
        - mood_set("hype")
        - eval("<AudioScript>") etc
    """
    try:
        if "(" in action and action.endswith(")"):
            name = action.split("(", 1)[0].strip()
            args = action[action.find("(")+1:-1]
            func = command_registry.get(name)
            if func is None:
                say(f"[MIDI map] unknown command: {name}", "⚠️")
                return
            arglist = [a.strip().strip('"\'') for a in args.split(",")] if args else []
            func(*arglist)
        elif action.startswith("tag:"):
            # look up settings and apply
            tag = action.split(":",1)[1].strip()
            settings_cmds = t2s.tag_to_commands(tag)    # returns list of AS lines
            for line in settings_cmds:
                _fire_action(line, ev)
        else:
            say(f"[MIDI map] invalid action: {action}", "⚠️")
    except Exception as e:
        say(f"[MIDI map] action error: {e}", "❌")

def _event_signature(ev: dict) -> str:
    # create a compact signature string
    parts = [ev.get("type", "unknown")]
    if "channel" in ev: parts.append(f"ch={ev['channel']}")
    if "note" in ev: parts.append(f"key={ev['note']}")
    if "velocity" in ev: parts.append(f"vel={ev['velocity']}")
    if "control" in ev: parts.append(f"cc={ev['control']}")
    return ":".join(parts)

def midi_tick():
    global _midi_in, _last_event_sig

    if not _midi_enabled or _midi_in is None:
        return

    for ev in _midi_in.iter_pending():
        sig = _event_signature(ev)
        _last_event_sig = sig
        _handle_midi_event(ev)

def midi_tags_last():
    say(f"Last tags: {_last_tags}")

def register():
    return {
        "midi_ports": midi_ports,
        "midi_listen": midi_listen,
        "midi_stop": midi_stop,
        "midi_map_load": midi_map_load,
        "midi_tick": midi_tick,
        "midi_tags_last": midi_tags_last,
    }

def _len(x):
    try:
        return len(x)
    except:
        return 0
