# audiomix
# AudioMIX
# performance_engine/modules/audio_recorder.py

# AudioMIX Audio Recorder
"""
Real-time audio recording via PyAudio with WAV file output.

Provides a singleton recorder instance that can be controlled
from the AudioScript shell.
Supports continuous recording, timed one-shot captures,
and device/format configuration.

Registered AudioScript commands:
  record - start recording to a file, or timed oneshot
  record_stop - stop recording and save the file
  record_set_input - set the input device by index
  record_set_format - set sample rate and channel count
  list_inputs - list avail audio input devices

Usage in AS shell:
  list_inputs()
  record_set_input(0)
  record_set_format(48000, 1)
  record(output.wav)
  record_stop()
  
  * Timed oneshot - records for N seconds then saves automatically
  record(output.wav, 5)

Output format:
  WAV, 16-bit PCM, mono by default (48000 Hz)
  Configurable via record_set_format()
"""

import threading
import time
from typing import Optional, List
import wave

try:
    import pyaudio as _pyaudio_module
    _PYAUDIO_AVAILABLE = True
except ImportError:
    _pyaudio_module = None    # type: ignore[assignment]
    _PYAUDIO_AVAILABLE = False

try:
    from performance_engine.modules.shared import say
except ImportError:
    # fallback for direct testing
    def say(text: str, emoji: str = "") -> None:
        print (f"{emoji} {text}" if emoji else text)

# Recorder class
# Singleton-style recorder
class PyAudioRecorder:
    """
    Singleton-style audio recorder wrapping PyAudio stream
    capture.
    Records audio from a configured input device to an
    in-memory buffer, then writes it to a WAV file on stop.
    Supports both continuous and timed one-shot recording modes.
    """
    def __init__(self):
        self._pa: Optional[object]= None
        self._stream: Optional[object] = None
        self._format: Optional[int] = None
        self._frames: List[bytes] = []
        self._running: bool = False
        self._filename: str = ""
        self._thread: Optional[threading.Thread] = None

        # sys default
        self.device_index: Optional[int] = None
        # safe default on Linux
        self.samplerate: int = 48000
        # default start at mono; can be set to 2
        self.channels: int = 1
        self.chunk: int = 1024

    # Internal helpers
    def _ensure_audio(self) -> None:
        """
        Lazily initialize PyAudio on first use.
        """
        if self._pa is None:
            if not _PYAUDIO_AVAILABLE:
                raise RuntimeError(
                    "pyaudio not installed. Run: pip installl pyaudio"
                )
            self._pa = _pyaudio_module.PyAudio() # type: ignore[union-attr]
            self._format = _pyaudio_module.paInt16 # type: ignore[union-attr]

    # Public interface
    def start(self, filename: str) -> None:
        """
        Start continuous recording to a filename.
        Recording runs on a background daemon thread until
        stop() is called.
        
        Args:
          filename: Output WAV file path
        """
        self._ensure_audio()
        if self._running:
            say(" [record] Already running - call record_stop() first.", "⚠️")
            return
        
        assert self._pa is not None
        assert self._format is not None

        try:
            #open input stream
            self._stream = self._pa.open( # type: ignore[union-attr]
                format=self._format,
                rate=self.samplerate,
                channels=self.channels,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk
            )
            self.frames = []
            self.running = True
            self._filename = filename

            say(
                f" [record] Started -> {filename} "
                f"@ {self.samplerate} Hz / ch={self.channels}", "⏺️"
            )

            def _record_loop():
                while self.running:
                   try:
                       assert self._stream is not None
                       data = self.stream.read( # type: ignore[union-attr]
                           self.chunk, exception_on_overflow=False
                        )
                       self.frames.append(data)
                   except Exception as e:
                       say(f" [record] Stream error: {e}", "❌")
                       break

            self.thread = threading.Thread(target=_record_loop, daemon=True)
            self.thread.start()

        except Exception as e:
            say(f" [record] Failed to start: {e}", "❌")

    def stop(self) -> None:
        """
        Stop recording and write captured audio to the
        WAV file
        """
        if not self.running:
            say(" [record] Not currently recording", "⚠️")
            return

        assert self._pa is not None
        assert self._stream is not None
        assert self._format is not None

        self._running = False

        self.stream.stop_stream() # type: ignore[union-attr]
        self.stream.close()       # type: ignore[union-attr]
        self.stream = None

        wf = wave.open(self._filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(
            self._pa.get_sample_size(self.format) # type: ignore[union-attr]
        )
        wf.setframerate(self.samplerate)
        wf.writeframes(b"".join(self._frames))
        wf.close()

        say(f" [record] Saved -> {self._filename}", "💾")

    def oneshot(self, filename: str, seconds: float) -> threading.Thread:
        """
        Record for a fixed duration then save automatically.
        
        Args:
          filename: Output WAV file path
          seconds: Recording duration in seconds.
        
        Returns:
          the background thread handling the time stop
        """
        self.start(filename)

        def _stop_later():
            try:
                for remaining in range(int(seconds), 0, -1):
                    print (f"[⏳] {remaining} sec remaining...", end="\r")
                    time.sleep(1)
                print()
                self.stop()
            except Exception as e:
                say(f"[record] Oneshot error: {e}", "❌")

        t = threading.Thread(target=_stop_later, daemon=True)
        t.start()
        # handy for programmatic calls
        return t

    def set_input(self, index: Optional[int]) -> None:
        """
        Set the input device by index.
        Pass None to use the system default.
        
        Args:
          index: Device index from list_inputs(), or None
                 for default.
        """
        self.device_index = int(index) if index is not None else None
        say(f"[record] Input device set to: {self.device_index}", "🎤")

    def set_format(self, rate: Optional[int] = None, channels: Optional[int] = None) -> None:
        """
        Set recording sample rate and channel count
        
        Args:
          rate: Sample rate in Hz (e.g., 44100, 48000)
          channels: Number of channels - 1 for mono, 2 for    
                    stereo
        """
        if rate is not None:
            self.samplerate = int(rate)
        if channels is not None: 
            self.channels = int(channels)
        say(f"[record] Format -> {self.samplerate} Hz / ch={self.channels}", "🎚️")

    def list_inputs(self) -> None:
        """
        Print all available audio input devices with
        their indices
        """
        self._ensure_audio()
        assert self._pa is not None

        count = self._pa.get_device_count() # type: ignore[union-attr]
        say("Available input devices:", "🎤")
        for i in range(count):
            info = self._pa.get_device_info_by_index(i) # type: ignore[union-attr]
            max_ch = int(info["maxInputChannels"])
            if max_ch > 0:
                say(f" [{i}] {info['name']} (ch={max_ch})")

# Singleton instance
_REC: Optional[PyAudioRecorder] = None

def _rec() -> PyAudioRecorder:
    """
    Return the singleton PyAudioRecorder
    Creates if needed.
    """
    global _REC
    if _REC is None:
        _REC = PyAudioRecorder()
    return _REC

# AudioScript (AS) command functions
def record(*args) -> None:
    """
    Start recording or begin a timed oneshot capture.
    
    Args (from AudioScript shell):
      args[0]: Output filename (req)
      args[1]: Duration in seconds (optional - omit for contin)
    
    Examples:
      record(output.wav)
      record(output.wav, 5)
    """
    if not args:
        say("[record] Usage: record(filename.wav or record(filename.wav, seconds)", "⚠️")
        return
    filename = str(args[0]).strip().strip('"')
    seconds = float(args[1]) if len(args) > 1 else None
    rec = _rec()
    if seconds is not None:
        rec.oneshot(filename, seconds)
    else:
        rec.start(filename)

def record_stop(*_) -> None:
    """
    Stop the current recording and save the file
    """
    _rec().stop()

def record_set_input(*args) -> None:
    """
    Set the recording input device.
    
    Args:
      args[0]: Device index (integer) or omit for sys default
    """
    index = int(args[0]) if args else None
    _rec().set_input(index)

def record_set_format(*args) -> None:
    """
    Set recording sample rate and channel count.
    
    Args:
      args[0]: Sample rate in Hz (optional)
      args[1]: Channel count (optional)
    """
    rate = int(args[0]) if len(args) > 0 else None
    channels = int(args[1]) if len(args) > 1 else None
    _rec().set_format(rate, channels)

def list_inputs(*_) -> None:
    """
    List all available audio input devices
    """
    _rec().list_inputs()

# AudioScript command registration
def register() -> dict:
    """
    Register audio recorder commands with the AudioScript
    shell.
    Called automatically by the module loader in
    audioscript_runtime.py
    """
    return {
        "record": record,
        "record_stop": record_stop,
        "record_set_input": record_set_input,
        "record_set_format": record_set_format,
        "list_inputs": list_inputs
    }

# Direct test entrypoint
if __name__ == "__main__":
    r = PyAudioRecorder()
    r.list_inputs()
    r.set_input(0)    # or None
    r.set_format(48000, 1)
    r.oneshot("test_direct.wav", 5)
