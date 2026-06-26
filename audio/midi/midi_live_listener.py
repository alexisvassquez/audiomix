# audiomix
# AudioMIX
# audio/midi/midi_live_listener.py

import os
os.environ.setdefault('MIDO_BACKEND', 'mido.backends.rtmidi')
os.environ.setdefault('RTMIDI_API', 'LINUX_ALSA')

import sys, time, json, queue, threading
from typing import Dict, Any, Optional
import mido

# Hot mapping: MIDI -> AudioScript
DEFAULT_MAP = {
    "note_on:C4": "lights.front_strip.flash('red', duration=0.25)",
    "note_on:D4": "lights.front_strip.flash('blue', duration=0.25)",
    "note_on:E4": "lights.front_strip.flash('green', duration=0.25)",
    "cc:1":       "fx.modwheel(depth=0.5)",
    "cc:64":      "fx.sustain(toggle=True)",
    "note_on:G3@vel>100": "fx.chorus.enable()",
}

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def note_number_to_name(n: int) -> str:
    return f"{NOTE_NAMES[n % 12]}{(n // 12) - 1}"

def load_map(path: Optional[str]) -> Dict[str, str]:
    if not path: return DEFAULT_MAP
    with open(path, 'r') as f:
        return json.load(f)

def match_mapping(msg, mapping: Dict[str, str]) -> Optional[str]:
    """
    Examples supported:
        - note_on:C4
        - note_off:F#3
        - cc:64
        - note_on:G3@vel>100
    """
    if msg.type in ("note_on", "note_off"):
        key = f"{msg.type}:{note_number_to_name(msg.note)}"
        # exact match
        if key in mapping: return mapping[key]
        # vel condition variant
        for mkey, action in mapping.items():
            if mkey.startswith(f"{msg.type}:{note_number_to_name(msg.note)}@vel>"):
                try:
                    thresh = int(mkey.split("@vel>")[1])
                    if getattr(msg, "velocity", 0) > thresh:
                        return action
                except ValueError:
                    pass
    elif msg.type == "control_change":
        key = f"cc:{msg.control}"
        if key in mapping: return mapping[key]
    return None

class MidiListener:
    def __init__(self, port_name: str, mapping: Dict[str, str], out_queue: queue.Queue):
        self.port_name = port_name
        self.mapping = mapping
        self.q = out_queue
        self.stop = False

    def loop(self):
        print (f"🎹  Opening MIDI input: {self.port_name}")
        try:
            with mido.open_input(self.port_name) as port:
                last_ts = time.time()
                while not self.stop:
                    for msg in port.iter_pending():
                        # basic debouncing / backpressure print rate
                        now = time.time()
                        if now - last_ts > 0.01:
                            last_ts = now
                        # Route message -> AudioScript (from default map)
                        action = match_mapping(msg, self.mapping)
                        if action:
                            self.q.put({"type":"audioscript_cmd", "cmd": action, "src": "midi"})
                            print (f"-> MIDI {msg.type}: {str(msg)} => AudioScript: {action}")
                    time.sleep(0.001)
        except IOError as e:
            print (f"[ERROR] Could not open MIDI port '{self.port_name}': {e}")

def select_port(allow_virtual=True):
    ins = mido.get_input_names()
    if not ins and allow_virtual:
        print ("No physical MIDI inputs found; creating virtual input 'AudioMIX-Listener'.")
        return "VIRTUAL"    # sentinel
    if not ins:
        raise RuntimeError("No MIDI inputs found. Plug a device or start a virtual port.")

    print ("Available MIDI inputs:")
    for i, name in enumerate(ins):
        print (f"  [{i}] {name}")
    sel = input("Select input index: ").strip()
    return ins[int(sel)]

def audioscript_consumer(cmd_queue: queue.Queue):
    """
    TODO: integrate with AudioScript shell.
    TODO: import runtime, dispatch.
    """
    while True:
        item = cmd_queue.get()
        if item is None: break
        if item["type"] == "audioscript_cmd":
            # Placeholder
            # TODO: call into AudioScript runtime
            print (f"🧠  [DISPATCH] {item['cmd']}")

if __name__ == "__main__":
    # Map JSON path
    mapping_path = sys.argv[1] if len(sys.argv) > 1 else None
    mapping = load_map(mapping_path)
    port_name = select_port()
    if port_name == "VIRTUAL":
        # open virtual port
        inport = mido.open_input("AudioMIX-Listener", virtual=True)
    else:
        inport = mido.open_input(port_name)

    q = queue.Queue()
    t_consumer = threading.Thread(target=audioscript_consumer, args=(q,), daemon=True)
    t_consumer.start()

    listener = MidiListener(port, mapping, q)
    try:
        listener.loop()
    except KeyboardInterrupt:
        print ("\nStopping...")
        listener.stop = True
        q.put(None)
