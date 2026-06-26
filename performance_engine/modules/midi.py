# audiomix
# AudioMIX
# performance_engine/modules/midi.py

import threading, time, queue, re, os
from typing import Callable, Dict, Any, Optional, List
import mido
from mido import Message
from performance_engine.utils.shell_output import say
from performance_engine.modules.context import command_registry

_event_q: "queue.Queue[dict]" = queue.Queue(maxsize=4096)
_listener_thread: Optional[threading.Thread] = None
_stop_flag = threading.Event()
_current_inport = None
_mappings: List[dict] = []    # [{match: callable, action: callable, quant: '1/4'}]
_quant_grid = None    # '1/4', '1/8', or None
_tempo_bpm = 120.0
_last_clock_ts = None
_clock_ticks = 0

def _now() -> float:
    return time.monotonic()

def _to_event(msg: Message) -> dict:
    """Normalize mido.Message -> dict event.""" 
    d = {"ts": _now(), "type": msg.type}
    for k, v in msg.dict().items():
        if k != 'type':
            d[k] = v
    return d

def _listener(port_name: str):
    global _current_inport, _clock_ticks, _last_clock_ts
    say(f"[MIDI] Opening input: {port_name}", "🎹")
    _current_inport = mido.open_input(port_name)
    while not _stop_flag.is_set():
        for msg in _current_inport.iter_pending():
            ev = _to_event(msg)
            # MIDI clock handling
            if ev["type"] == "clock":
                _clock_ticks += 1
                _last_clock_ts = ev["ts"]
                # 24 ticks per quarter note -> infer tempo over rolling window (if needed)
            _event_q.put(ev)
        time.sleep(0.001)    # avoid busy-wait
    try:
        _current_inport.close()
    except Exception:
        pass
    say("[MIDI] Listener stopped.", "🛑")

# Public API / Commands
def midi_ports():
    if not mido:
        say("mido not available. Install `mido` and `python-rtmidi`.", "⚠️")
        return
    ins = mido.get_input_names()
    outs = mido.get_output_names()
    say("Inputs:", "🎛️"); [say(f" - {i}") for i in ins]
    say("Outputs:", "🔌"); [say(f" - {o}") for o in outs]

def midi_listen(port_substr: str = ""):
    """Start realtime MIDI listener on first port matching substring (or first device)."""
    if not mido:
        say("mido not available. Install `mido` and `python-rtmidi`.", "⚠️")
        return
    global _listener_thread
    if _listener_thread and _listener_thread.is_alive():
        say("MIDI listener already running.", "ℹ️")
        return
    ports = [p for p in mido.get_input_names() if port_substr.lower() in p.lower()] or mido.get_input_names()
    if not ports:
        say("No MIDI inputs found.", "⚠️")
        return
    _stop_flag.clear()
    _listener_thread = threading.Thread(target=_listener, args=(ports[0],), daemon=True)
    _listener_thread.start()
    say(f"Listening on: {ports[0]}", "🎤")

def midi_stop():
    _stop_flag.set()

def midi_quantize(grid: str = "1/8"):
    """Set quantization grid for mapping ('1/4', '1/8', '1/16', or 'off')."""
    global _quant_grid
    if grid.lower() in ("off", "none", "0"):
        _quant_grid = None
        say("Quantize OFF", "🔇")
    else:
        _quant_grid = grid
        say(f"Quantize set: {grid}", "🔈")

def _beats_to_seconds(beats: float) -> float:
    return (60.0 / max(_tempo_bpm, 1e-6)) * beats

def _grid_to_beats(grid: Optional[str]) -> float:
    if not grid: 
        return 0.0
    den = int(grid.split("/")[1])
    return 1.0 / den    # ex; 1/8 -> 0.125 beats

def _schedule_time(ts: float) -> float:
    """Return scheduled time aligned to grid; ts is event arrival time."""
    if not _quant_grid:
        return ts
    grid_beats = _grid_to_beats(_quant_grid)
    # derive current beat fraction from local clock
    # local clock: phase = (ts % beat_len)/beat_len
    beat_len = _beats_to_seconds(1.0)
    phase = (ts % beat_len) / max(beat_len, 1e-9)
    # next grid boundary:
    step = grid_beats
    step_s = _beats_to_seconds(step)
    boundary = ((int((ts/step_s)) + 1) * step_s)
    return boundary

def midi_map(pattern: str, action: str):
    """
    Map a MIDI pattern to an AudioScript/engine action.
    pattern examples:
        "note_on:ch=1:key=36", "cc:ch=1:cc=1" or "note_on:*"
    action examples:
        'play("<file_name>.wav")'
        'glow("purple")'
        'fx.add("track1","compressor",{"ratio":3})' 
    """
    compiled = re.compile("^" + pattern.replace("*", ".*") + "$")
    def match(ev: Dict[str, Any]) -> bool:
        # turn event dict into compact tag string for matching
        parts = [ev["type"]]
        ch = ev.get("channel")
        if ch is not None: parts.append(f"ch={ch}")
        if "note" in ev: parts.append(f"key={ev['note']}")
        if "velocity" in ev: parts.append(f"vel={ev['velocity']}")
        if "control" in ev: parts.append(f"cc={ev['control']}")
        s = ":".join(map(str, parts))
        return bool(compiled.match(s))
    def act(ev: Dict[str, Any]):
        # AudioScript function lookup in command registry
        from .performance_engine.modules.context import command_registry as cr
        try:
            if "(" in action and action.endswith(")"):
                cmd = action.strip()
                # Evaluate by passing line into runtime parser via registry
                # Extract function name and args
                name = cmd.split("(",1)[0]
                args = cmd[cmd.find("(")+1:-1]
                f = cr.get(name)
                if f:
                    # naive split, supports commas
                    arglist = [a.strip().strip('"\'') for a in args.split(",")] if args else []
                    f(*arglist)
                else:
                    say(f"[MIDI map] Unknown command: {name}", "⚠️")
            else:
                say(f"[MIDI map] Invalid action: {action}", "⚠️")
        except Exception as e:
            say(f"[MIDI map] Action error: {e}", "❌")
    _mappings.append({"match": match, "action": act})
    say(f"[MIDI] mapped {pattern} -> {action}", "🎼")

def midi_tick():
    """Call often from engine loop; drains event queue and executes mappings with quantize."""
    now = _now()
    drained = 0
    while not _event_q.empty():
        ev = _event_q.get()
        drained += 1
        # schedule time; quantize by sleeping until boundary
        # scheduled for immediate execution
        exec_at = _schedule_time(ev["ts"])
        sleep_for = max(0.0, exec_at - now)
        if sleep_for > 0.0:
            time.sleep(min(sleep_for, 0.02))    # cap tiny waits
        for m in _mappings:
            if m["match"](ev):
                m["action"](ev)
    if drained:
        say(f"[MIDI] processed {drained} event(s)", "🕛")

def register():
    return {
        "midi_ports": midi_ports,
        "midi_listen": midi_listen,
        "midi_stop": midi_stop,
        "midi_map": midi_map,
        "midi_quantize": midi_quantize,
        "midi_tick": midi_tick,
    }
