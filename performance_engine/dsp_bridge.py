# AudioMIX
# performance_engine/dsp_bridge.py

"""
AudioMIX DSP Bridge

Connects the Python AudioMIX runtime to the C++ 
DSP engine (audiomix library) via a subprocess pipe 
using NDJSON over stdin/stdout.

The bridge subscribes to DSP events on the EventBus and
forwards them as NDJSON commands to the C++ controlLoop.
Responses (acks, errors) are read back from the process
stdout on a dedicated daemon thread.

Launch behavior:
  launch=True (default) - bridge attempts to start the
  audiomix binary. 
  If the binary is not found, a warning is printed and 
  bridge runs in no-op mode.
  The Python shell continues to function normally.

  launch=False - bridge runs in no-op mode intentionally. 
  Use this for stage control scenarios where audio output is
  handled externally (mixer, DJ setup), or for Python-only
  development sessions.

CLI flag:
  --no-dsp - passed by audioscript_runtime.py to set
  launch=False at startup

Event naming convention:
  "dsp.eq.set" -> {"cmd": "eq.set", ...}
  "dsp.compressor.set" -> {"cmd": "compressor.set", ...}
  "dsp.gain.set" -> {"cmd": "gain.set", ...}
  "dsp.ping" -> {"cmd": "ping"}
"""

from __future__ import annotations
import json
import os
import subprocess
import threading
from typing import Optional

#Path to the compiled C++ binary, relative to project root
DSP_BINARY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "build", "audiomix"
)

class DSPBridge:
    """
    Translates AudioMIX EventBus events into NDJSON
    commands for the C++ audiomix DSP engine
    
    When launch=True and the binary exists, the bridge
    starts the process and holds references to its
    stdin/stdout pipes.

    When launch=False or the binary is not found, all
    send operations are silent no-ops so the rest of the
    system continues unaffected.
    """

    def __init__(self, event_bus, launch: bool = True, headless: bool = True, verbose: bool = False):
        self._bus = event_bus
        self._lock = threading.Lock()
        self._verbose = verbose
        self._process: Optional[subprocess.Popen] = None
        self._active = False

        if launch:
            self._launch(headless)
        else:
            if self._verbose:
                print(
                    "[DSPBridge] Running in no-op mode (launch=False)."
                    "Audio thread will not be started."
                )

        # register all DSP event handlers on the bus
        # regardless of launch state
        # in no-op mode, _send() will silently do nothing
        self._register_handlers()

        # start ack listener thread only if process is running
        if self._active:
            ack_thread = threading.Thread(
                target=self.listen_for_acks, daemon=True
            )
            ack_thread.start()
    
    # Process launch
    def _launch(self, headless: bool):
        """
        Attempts to launch the audiomix binary as a
        subprocess.
        Sets self._active = True on success, prints a
        warning on failure.
        """
        if not os.path.isfile(DSP_BINARY):
            print(
                f"[DSPBridge] ! Binary not found at: {DSP_BINARY}\n"
                f"[DSPBridge]   Run 'cd build && make' to build it.\n"
                f"[DSPBridge]   Running in no-op mode - shell will work "
                f"but audio engine is inactive."
            )
            return

        args = [DSP_BINARY]
        if headless:
            args.append("--headless")

        try:
            self._process = subprocess.Popen(
                args, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=None, 
                text=True, 
                bufsize=1,    # line-buffered
            )
            self._active = True
            if self._verbose:
                mode = "headless" if headless else "full audio"
                print(f"[DSPBridge] ✓ AudioMIX launched ({mode}, PID {self._process.pid})")
        except OSError as e:
            print(f"[DSPBridge] ! Failed to launch AudioMIX: {e}")
            print("[DSPBridge]    Running in no-op mode.")

    # Registration
    def _register_handlers(self):
        self._bus.on("dsp.eq.set", self._handle_eq_set)
        self._bus.on("dsp.compressor.set", self._handle_compressor_set)
        self._bus.on("dsp.gain.set", self._handle_gain_set)
        self._bus.on("dsp.ping", self._handle_ping)

    # Handlers
    # one per DSP command type
    def _handle_eq_set(self, payload: dict):
        """
        eq.set
        keys: band, freq, gain_db, q, type
        """
        self._send({"cmd": "eq.set", **payload})

    def _handle_compressor_set(self, payload: dict):
        """
        compressor.set
        keys: threshold, ratio, attack_ms, release_ms
        """ 
        self._send({"cmd": "compressor.set", **payload})

    def _handle_gain_set(self, payload: dict):
        """
        gain.set
        keys: gain_db (float)
        """
        self._send({"cmd": "gain.set", **payload})

    def _handle_ping(self, payload=None):
        self._send({"cmd": "ping"})

    # Core send
    def _send(self, message: dict):
        """
        serializes to NDJSON, writes to DSP process stdin
        silent no-op if the process is not running
        """
        if not self._active or self._process is None:
            return
        
        line = json.dumps(message, separators=(',', ':'))
        with self._lock:
            try:
                assert self._process is not None
                assert self._process.stdin is not None
                self._process.stdin.write(line + "\n")
                self._process.stdin.flush()
                if self._verbose:
                    print(f"[DSPBridge -> DSP] {line}")
            except (BrokenPipeError, OSError) as e:
                print(f"[DSPBridge] ! Lost connection to DSP engine: {e}")
                self._active = False

    # Ack listener
    def listen_for_acks(self):
        """
        Reads NDJSON responses from the DSP engine stdout.
        Runs on a daemon thread, exits automatically when
        the process ends.
        """
        try:
            assert self._process is not None
            assert self._process.stdout is not None
            for raw_line in self._process.stdout:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    msg = json.loads(raw_line)
                    cmd = msg.get("cmd")
                    if cmd == "ack":
                        if self._verbose:
                            print(f"[DSPBridge <- DSP] ack: {msg.get('ack')}")
                    elif cmd == "pong":
                        if self._verbose:
                            print("[DSPBridge <- DSP] pong received")
                    elif cmd == "error":
                        print(f"[DSPBridge <- DSP] ! DSP error: {msg.get('error')}")
                except json.JSONDecodeError:
                    print(f"[DSPBridge <- DSP] malformed response: {raw_line}!r")
        except (OSError, ValueError):
            # process ended - thread exits cleanly
            pass

    # Shutdown
    def shutdown(self):
        """
        Gracefully terminate the DSP process.
        Called automatically at AudioMIX shell exit.
        """
        if self._process and self._active:
            if self._verbose:
                print("[DSPBridge] Shutting down DSP engine...")
            try:
                assert self._process is not None
                assert self._process.stdin is not None
                self._process.stdin.close()
                self._process.terminate()
                self._process.wait(timeout=3)
                if self._verbose:
                    print("[DSPBridge] DSP engine stopped.")
            except (OSError, subprocess.TimeoutExpired):
                self._process.kill()
            finally:
                self._active = False

# Convenience factory
def attach_dsp_bridge(event_bus, launch=True, headless=True, verbose=False) -> DSPBridge:
    """
    Creates a DSPBridge, attaches it to the given EventBus,
    and optionally launches the AudioMIX C++ process.

    Args:
      event_bus: The shared AudioMIX EventBus singleton.
      launch: If True, attempt to launch the audiomix binary.
        If false, run in no-op mode (stage control, dev mode).
      headless: If True, launch audiomix with --headless flag
        (no PortAudio, hardware agnostic).
      verbose: If True, print all NDJSON traffic to the terminal.
    """
    return DSPBridge(event_bus, launch=launch, headless=headless, verbose=verbose)
