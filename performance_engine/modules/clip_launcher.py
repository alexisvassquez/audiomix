# AudioMIX
# performance_engine/modules/clip_launcher.py

import os, json, subprocess, shlex, threading, tempfile
from typing import Dict, List, Any, Optional
import queue, time
import soundfile as sf
from performance_engine.utils.shell_output import say
from performance_engine.modules.context import command_registry
from performance_engine.modules.sampler import sampler_play
from performance_engine.modules.sampler import _BANKS as _SAMPLER_BANKS

_CLIPS: Dict[str, Dict[str, Any]] = {}
_PLAYERS: Dict[str, "ClipPlayer"] = {}
_GROUP_INDEX: Dict[str, set] = {}

# Evaluator looks up function by name in command_registry
# Passes parsed args in string list, split by commas
def _eval_action(action: str):
    try:
        if "(" in action and action.endswith(")"):
            name = action.split("(", 1)[0].strip()
            args_str = action[action.find("(")+1:-1]
            func = command_registry.get(name)
            if not func:
                say(f"[clip] Unknown command: {name}", "⚠️")
                return
            arglist = []
            if args_str.strip():
                parts = [p.strip() for p in args_str.split(",")]
                arglist = [p.strip().strip('"\'') for p in parts]
            func(*arglist)
        else:
            say(f"[clip] Invalid action string: {action}", "⚠️")
    except Exception as e:
        say(f"[clip] Action error: {e}", "❌")

def _ms_to_frames(ms: float, sr: int) -> int:
    return max(0, int((ms/1000.0)*sr))

# Clip Player
# Looping clips
class ClipPlayer:
    def __init__(self, name: str, path: str, start_ms: Optional[float], end_ms: Optional[float],
                loop: int, gain: float = 1.0):
        self.name = name
        self.path = path
        self.loop = loop    # -1 = infinite, 0 = once, N repeats
        self.gain = max(0.0, float(gain))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._start_ms = start_ms
        self._end_ms = end_ms
        self._tmp_path: Optional[str] = None
        self._proc: Optional[subprocess.Popen] = None

    def start(self):
        self._thread.start()

    # Allow thread to exit then cleanup temp
    def stop(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass

    def _render_region_to_temp(self) -> Optional[str]:
        try:
            data, sr = sf.read(self.path, dtype="float32", always_2d=True)
            start_f = _ms_to_frames(self._start_ms, sr) if self._start_ms else 0
            end_f = _ms_to_frames(self._end_ms, sr) if self._end_ms else len(data)
            end_f = min(end_f, len(data))
            if end_f <= start_f:
                say(f"[clip] Invalid region for {self.name}: start>=end", "⚠️")
                return None
            region = data[start_f:end_f] * self.gain

            # writes region to a temp .wav file
            # play once with aplay (fire-and-wait)
            tmp = tempfile.NamedTemporaryFile(prefix="clip_", suffix=".wav", delete=False)
            tmp_path = tmp.name
            tmp.close()
            sf.write(tmp_path, region, sr)
            return tmp_path
        except Exception as e:
            say(f"[clip] Render error for '{self.name}': {e}")
            return None

    # reuse same temp file for loops
    def _run(self):
        try:
            self._start_ms = getattr(self, "_start_ms", None)
            self._end_ms = getattr(self, "_end_ms", None)
            if not hasattr(self, "_start_ms"):
                self._start_ms = None
            if not hasattr(self, "_end_ms"):
                self._end_ms = None

            self._tmp_path = self._render_region_to_temp()
            if not self._tmp_path:
                return

            # False is stop was requested (default to True)
            def play_once() -> bool:
                if self._stop.is_set():
                    return False
                try:
                    # blocks playback to respect stop/loop
                    self._proc = subprocess.Popen(
                        ["aplay", self._tmp_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    # poll for completion/stop
                    while proc.poll() is None and not self._stop.is_set():
                        time.sleep(0.02)    # wait
                    if self._stop.is_set() and proc.poll() is None:
                        try:
                            self._proc.terminate()
                        except Exception:
                            pass
                        return False
                    return not self._stop.is_set()
                except FileNotFoundError:
                    say("[clip] 'aplay' not found. Install 'alsa-utils'.")
                    return False
                except Exception as e:
                    say(f"[clip] Playback error for '{self.name}': {e}")
                    return False

            # playback loop
            # initial playback + repeats
            repeats = self.loop
            if repeats == -1:    # infinite loop
                while not self._stop.is_set():
                    if not play_once():
                        break
            else:
                # repeats==0 means play once
                # N>0 x plays
                count = max(1, repeats+1)
                for _ in range(count):
                    if self._stop.is_set():
                        break
                    if not play_once():
                        break
        # Clean temp file
        finally:
            if self._tmp_path:
                try:
                    os.remove(self._tmp_path)
                except OSError:
                    pass

def _resolve_sampler_path(bank: str, alias: str) -> Optional[str]:
    b = _SAMPLER_BANKS.get(bank) or {}
    meta = b.get("sounds", {}).get(alias) if b else None
    p = meta.get("file") if meta else None
    return p if (p and os.path.exists(p)) else None

def _stop_choke_group(group: str):
    names = _GROUP_INDEX.get(group) or set()
    for nm in list(names):
        _clip_stop(nm)

def _clip_stop(name: str):
    pl = _PLAYERS.pop(name, None)
    if pl:
        pl.stop()
        say(f"[clip] Stopped '{name}'", "🛑")

# Clips Launcher
# Define a clip
# kind: "sampler" -> ref: alias + bank provided
# When kind: "file" -> ref: audio path + extension (.wav, .aif, etc)
# loop: "off", "inf", or int string
# start/end_ms: region in ms
# retrigger: "mono" or "poly"
# choke_group: optional -> triggering stops other clips in group
# gain: linear gain
def clip_add(name: str, kind: str, ref: str, bank: str = "",
             loop: str = "off", start_ms: str = "", end_ms: str = "",
             retrigger: str = "mono", choke_group: str = "", gain: str = "1.0"):
    kind = (kind or "").strip().lower()
    if kind not in ("sampler", "file"):
        say("Kind must be 'sampler' or 'file'", "⚠️")
        return

    path = None
    if kind == "file":
        path = ref
    else:    # sampler
        if not bank or not ref:
            say(f"[clip] File not found. For sampler kind, provide bank and alias: {ref}", "⚠️")
            return
        path = _resolve_sampler_path(bank, ref)
        if not path:
            say(f"[clip] Sampler file missing {bank}:{ref}", "⚠️")
            return

    if not os.path.exists(path):
        say(f"[clip] File not found: {path}", "⚠️")
        return

    # parse loop
    lval = str(loop).lower().strip()
    if lval in ("off", "0"):
        loop_n = 0
    elif lval in ("inf", "infinite", "true", "-1"):
        loop_n = -1
    else:
        try:
            loop_n = max(-1, int(lval))
        except Exception:
            loop_n = 0

    # region
    try:
        s_ms = float(start_ms) if start_ms else None
        e_ms = float(end_ms) if end_ms else None
    except Exception:
        s_ms, e_ms = None, None

    retrig = (retrigger or "mono").lower().strip()
    if retrig not in ("mono", "poly"):
        retrig = "mono"

    # gain
    g = 1.0
    try:
        g = max(0.0, float(gain))
    except:
        pass

    _CLIPS[name] = {
        "type": kind, "ref": ref, "bank": bank, "path": path,
        "loop": loop_n, "start_ms": s_ms, "end_ms": e_ms,
        "retrigger": retrig, "choke_group": choke_group, "gain": g,
    }
    if choke_group:
        _GROUP_INDEX.setdefault(choke_group, set()).add(name)
    say(f"[clip] Added '{name}' -> ({kind}) loop={loop} retrig={retrig} group={choke_group}", "✅")

def clip_list():
    if not _CLIPS:
        say("[clip] No clips defined", "ℹ️")
        return
    say("Clips:", "🎬")
    for k, v in _CLIPS.items():
        base = os.path.basename(v["path"]) if v.get("path") else "?"
        reg = f"{v['type']}:{v.get('bank', '')}:{v.get('ref', '')}".strip(":")
        extras = []
        if v["loop"] == -1: extras.append("loop=inf")
        elif v["loop"] > 0: extras.append(f"loop={v['loop']}")
        if v["start_ms"] is not None or v["end_ms"] is not None:
            extras.append(f"region={v.get('start_ms', '')}-{v.get('end_ms', '')}")
        if v["choke_group"]: extras.append(f"group={v['choke_group']}")
        extras.append(f"retrigger={v['retrigger']}")
        extras.append(f"gain={v['gain']}")
        say(f" - {k}: {reg} -> {base} | {' '.join(extras)}")

def clip_remove(name: str):
    if name in _CLIPS:
        _CLIPS.pop(name, None)
        _clip_stop(name)
        # also remove from any choke group
        for g in list(_GROUP_INDEX.keys()):
            _GROUP_INDEX[g].discard(name)
        say(f"[clip] Removed: '{name}'", "🪣")
    else:
        say(f"[clip] Not found: {name}", "⚠️")

def clip_trigger(name: str):
    c = _CLIPS.get(name)
    if not c:
        say(f"[clip] Not found: {name}", "⚠️")
        return

    # choke first if group present
    grp = c.get("choke_group") or ""
    if grp:
        _stop_choke_group(grp)

    # mono retrigger
    if c.get("retrigger") == "mono":
        _clip_stop(name)

    # launch player
    pl = ClipPlayer(
        name=name,
        path=c["path"],
        start_ms=c.get("start_ms"),
        end_ms=c.get("end_ms"),
        loop=c.get("loop", 0),
        gain=c.get("gain", 1.0),
    )
    _PLAYERS[name] = pl
    pl.start()
    say(f"[clip] Trigger '{name}'", "▶️")

def clip_stop(name: str):
    _clip_stop(name)

def clip_stop_group(group: str):
    if not group in _GROUP_INDEX:
        say(f"[clip] Group not found: {group}", "⚠️")
        return

# AS Commands for MIDI mapping
def register():
    return {
        "clip.add": clip_add,
        "clip.list": clip_list,
        "clip.remove": clip_remove,
        "clip.trigger": clip_trigger,
        "clip.play": clip_trigger,
        "clip.stop": clip_stop,
        "clip.stop_group": clip_stop_group,
    }
