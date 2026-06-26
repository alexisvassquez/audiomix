# AudioMIX
# performance_engine/modules/audience_listener.py

"""
AudioMIX Audience Listener

Real-time crowd energy detection using ALSA
microphone capture.

Analyzes incoming audio for amplitude, spectral flux,
and high-freq content to produce a continuous energy
reading [0.0 .. 1.0] and detect discrete crowd events
(e.g., cheeing, applause)

This module forms the perceptual input layer of the
AudioMIX live performance loop:
  Mic -> audience_listener -> crowd energy -> mood_engine
  -> DSP/LED response

The listener runs on a background daemon thread and updates
shared state continuously. Other modules read from it via
get_crowd_state().

Registered AudioScript commands:
  crowd.calibrate - calibrate noise floor and peak lvls for
    the venue
  crowd.start - start the background listener thread
  crowd.stop - stop the background listener thread
  crowd.status - print the current crowd energy and event
    state
  crowd.energy - print the current energy value only

Calibration data is saved to:
  performance_engine/.cal/venue.json

Usage in AudioScript (AS) shell:
  crowd.calibrate(quick)
  crowd.start()
  crowd.status()
  crowd.stop()
"""

import queue, threading, time, math, json, os, struct
import numpy as np

try:
    import alsaaudio
except ImportError:
    alsaaudio = None

_CAL_PATH = "performance_engine/.cal/venue.json"

# Shared state
# updated by the background worker thread
# read by get_crowd_state() and AudioScript commands.
_state = {
    "energy": 0.0,                 # [0.0, 0.1...] etc
    "events": {"cheer": False},
    "updated_at": 0.0,
}

# reference to the active stop flag
# None if listener is not running
_stop_flag: threading.Event | None = None

# File helpers
def _ensure_dir(p):
    """
    Create parent directories for path p if they don't exist.
    """
    d = os.path.dirname(p)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def load_calibration() -> dict:
    """
    Load venue calibration from disk
    Returns default values if no calibration file exists.
    """
    if os.path.exists(_CAL_PATH):
        with open(_CAL_PATH, "r") as f:
            return json.load(f)
    return {"db_floor": -55.0, "db_peak": -15.0}

def save_calibration(db_floor: float, db_peak: float):
    """
    Save value calibration values to disk.
    """
    _ensure_dir(_CAL_PATH)
    with open(_CAL_PATH, "w") as f:
        json.dump({"db_floor": db_floor, "db_peak": db_peak}, f, indent=2)

# Signal processing helpers
def dbfs(x: np.ndarray) -> float:
    """
    Compute RMS level of audio buffer x in dBFS.
    Small epsilon prevents log(0)
    """
    rms = np.sqrt(np.mean(np.square(x) + 1e-12))
    return 20.0 * math.log10(max(rms, 1e-9))

def _spectral_flux(prev_mag: np.ndarray, cur_mag: np.ndarray) -> float:
    """
    Compute half-wave rectified spectral flux between two
    magnitude spectra.
    High flux indicates a transient - clap, cheer burst, or
    sudden onset.
    """
    diff = np.clip(cur_mag - prev_mag, 0, None)
    return float(np.sum(diff) / len(diff) + 1e-9)

def _normalize_db(db: float, floor: float, peak: float) -> float:
    """
    Normalize a dBFS value to [0.0, 1.0] using calibrated
    floor and peak
    """
    db = np.clip(db, floor, peak)
    return float((db - floor) / max(peak - floor, 1e-6))

def _smooth(prev: float, new: float, a: float = 0.85) -> float:
    """
    Exponential moving average smoothing.
    Higher a = slower response, more stable reading.
    Lower a = faster response, more reactive to transients.
    """
    return float(a * prev + (1 - a) * new)

def _bytes_to_np_int16(buf: bytes) -> np.ndarray:
    """
    Convert raw ALSA PCM bytes to normalised float32 array
    [-1.0, 1.0]
    ALSA PCM_CAPTURE returns little-endian signed 16-bit
    by default
    """
    return np.frombuffer(buf, dtype=np.int16).astype(np.float32) / 32768.0

# Public state accessor
def get_crowd_state() -> dict:
    """
    Return a snapshot of the current crowd state.
    Returns:
      dict with keys:
        energy - float [0.0, 1.0], smoothed crowd energy level
        events - dict of detected events 
          (e.g., {"cheer": True/False})
        updated_at - float, unix timestamp of last update
    """
    return {
        "energy": _state["energy"],
        "events": dict(_state["events"]),
        "updated_at": _state["updated_at"],
    }

# Calibration
def calibrate(mode: str = "quick", device: str = "default", sr: int = 32000, period_size: int = 512, seconds: int = 3):
    """
    Calibrate the audience listener for the current venue.
    Measures the ambient noise floor and optionally the peak
    crowd level, saving results to the calibration file for use during performance.
    
    Args:
      mode: "quick" - measure floor only, estimate peak as
                      floor + 30dB
            "full" - measure floor, then prompt for crowd
                    cheer sample
      device: ALSA device name (default: "default")
      sr: sample rate in Hz (default: 32000)
      period_size: ALSA period size in frames (default: 512)
      seconds: duration of each measurement window in seconds
               (default: 3)
    """
    if alsaaudio is None:
        raise RuntimeError(
            "pyalsaaudio not installed. Run: pip install pyalsaaudio"
        )

    pcm = alsaaudio.PCM(
        type=alsaaudio.PCM_CAPTURE, 
        mode=alsaaudio.PCM_NORMAL, 
        device=device
    )
    pcm.setchannels(1)
    pcm.setrate(sr)
    pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    pcm.setperiodsize(period_size)

    def _collect(sec):
        end = time.time() + sec
        chunks = []
        while time.time() < end:
            length, data = pcm.read()
            if length > 0:
                chunks.append(_bytes_to_np_int16(data))
            else:
                time.sleep(0.002)
        return np.concatenate(chunks) if chunks else np.zeros(
            period_size, dtype=np.float32
        )

    # noise floor
    x_floor = _collect(seconds)
    floor_db = dbfs(x_floor)

    if mode == "quick":
        peak_db = floor_db + 30.0
        print (f"[Audience] floor={floor_db:.1f} dBFS (quick mode)")
        save_calibration(floor_db, peak_db)
        pcm.close()
        return

    print ("[Audience] Now make some noise for a few seconds...")
    x_peak = _collect(seconds)
    peak_db = dbfs(x_peak)
    print (f"[Audience] floor={floor_db:.1f} / peak={peak_db:.1f} dBFS")
    save_calibration(floor_db, max(peak_db, floor_db + 10))
    pcm.close()

# Listener thread
# start ALSA capture on bkgrd thread
# returns stop_flag(threading.Event)
def start_listener(device: str = "default", sr: int = 32000, period_size: int = 512) -> threading.Event:
    """
    Start the background ALSA capture and energy analysis
    thread.
    The thread runs as a daemon and updates _state
    continuously.
    Call stop_listener() or set the returned stop_flag to
    stop it.
    
    Args:
      device: ALSA device name (default: "default")
      sr: sample rate in Hz (default 3200)
      period_size: ALSA period size in frames (default: 512)
    
    Returns:
      threading.Event - set this flag to stop the listener
      thread
    """
    global _stop_flag

    if alsaaudio is None:
        raise RuntimeError(
            "pyalsaaudio not installed. Run: pip install alsaaudio"
        )
    
    if _stop_flag is not None and not _stop_flag.is_set():
        print("[Audience] Listener is already running.")
        return _stop_flag

    cal = load_calibration()
    pcm= alsaaudio.PCM(
        type=alsaaudio.PCM_CAPTURE, 
        mode=alsaaudio.PCM_NONBLOCK, 
        device=device
    )
    pcm.setchannels(1)
    pcm.setrate(sr)
    pcm.setformat(alsaaudio.PCM_FORMAT_S16_LE)
    pcm.setperiodsize(period_size)

    _stop_flag = threading.Event()
    _local_stop = _stop_flag

    def worker(stop: threading.Event):
        prev_mag = None
        last_cheer = 0.0

        while not _local_stop.is_set():    # type: ignore[union-attr]
            length, data = pcm.read()
            if length <= 0:
                time.sleep(0.0015)
                continue

            x = _bytes_to_np_int16(data)
            db = dbfs(x)

            # spectral analysis for cheer/clap burst detection
            win = np.hanning(len(x))
            mag = np.abs(np.fft.rfft(x * win))
            if prev_mag is None:
                prev_mag = mag
            flux = _spectral_flux(prev_mag, mag)
            prev_mag = mag

            # high-freq ratio (2-6 kHz)
            # elevated during applause/cheering
            freqs = np.fft.rfftfreq(len(x), d=1.0/sr)
            hf_mask = (freqs >= 2000.0) & (freqs <= 6000.0)
            hf = float(np.mean(mag[hf_mask]) / (np.mean(mag) + 1e-9))

            # weighted energy
            # amplitude 60%, flux 30%, HF content 10%
            db_n = _normalize_db(db, cal["db_floor"], cal["db_peak"])
            raw = 0.6 * db_n + 0.3 * np.tanh(2.0*flux) + 0.1 * np.tanh(3.0*hf)
            raw = float(np.clip(raw, 0.0, 1.0))

            _state["energy"] = _smooth(_state["energy"], raw, a=0.85)
            _state["updated_at"] = time.time()

            # cheer event
            # high energy + high flux + 1s cooldown
            cheer_now = (
                db_n > 0.75 and 
                flux > 0.12 and 
                (time.time() - last_cheer) > 1.0
            )
            _state["events"]["cheer"] = bool(cheer_now)
            if cheer_now:
                last_cheer = time.time()

        pcm.close()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return _stop_flag

def stop_listener():
    """
    Stop the background listener thread gracefully.
    Sets the stop flag and resets shared state
    """
    global _stop_flag
    if _stop_flag is None:
        print("[Audience] Listener is not running.")
        return
    if _stop_flag.is_set():
        print("[Audience] Listener is not running")
        return
    _stop_flag.set()
    _stop_flag = None
    print("[Audience] Listener stopped.")

# AudioScript Command Registration
def register():
    """
    Register audience listener commands with the
    AudioScript shell.
    Called automatically by the module loader in
    audioscript_runtime.py
    """
    from performance_engine.modules.shared import say

    def _calibrate(mode="quick"):
        calibrate(mode)
        say(f"[Audience] Calibration saved (mode={mode})", "🎤")

    def _start(device="default"):
        start_listener(device=device)
        say("[Audience] Listener started - crowd energy monitoring active", "👂")

    def _stop():
        stop_listener()
        say("[Audience] Listener stopped", "🔇")

    def _status():
        state = get_crowd_state()
        energy = state["energy"]
        cheer = state["events"].get("cheer", False)
        age = time.time() - state["updated_at"]
        bar = "█" * int(energy * 20) + "░" * (20 - int(energy * 20))
        say(
            f"[CROWD] energy={energy:.2f} [{bar}] "
            f"cheer={'YES 🎉' if cheer else 'no'} "
            f"(updated {age:.1f}s ago)"
        )

    def _energy():
        say(f"[CROWD] energy={_state['energy']:.3f}", "📊")

    return {
        "crowd.calibrate": _calibrate,
        "crowd.start":     _start,
        "crowd.stop":      _stop,
        "crowd.status":    _status,
        "crowd.energy":    _energy,
    }
