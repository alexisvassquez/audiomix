# audiomix
# AudioMIX
# performance_engine/modules/audio_player.py

"""
AudioMIX Audio Player Module

Real-time audio playback via PyAudio with multi-format
support.
Handles WAV, MP3, FLAC, OGG, AAC, and any format supported
by pydub/ffmpeg.
All formats are normalized to 16-bit PCM internally before
playback.

This module is the canonical implementation of the `play`
AudioScript command.
The runtime's play() function delegates directly to this module.

Integrates with the lossless/lossy playback mode system
define in the audioscript_runtime.py - pass mode and codec
params to simulate real-world streaming quality during studio sessions.

Registered AudioScript commands:
  play          - plays an audio file
  player.stop   - stops current playback
  player.status - shows current playback state
  player.volume - sets playback volume (0.0 - 1.0)
  
Usage in AudioScript shell (examples):
  play(track.wav)
  play(track.mp3)
  player.volume(0.8)
  player.stop()
  player.status()
  
Dependencies:
  pyaudio - audio I/O (pip install pyaudio)
  pydub   - format conversion (pip install pydub)
  ffmpeg  - required by pydub for MP3/FLAC/OGG support
            (sudo apt install ffmpeg)
"""

import threading
import time
from typing import Optional, List

try:
    import pyaudio as _pyaudio_module
    _PYAUDIO_AVAILABLE = True
except ImportError:
    _pyaudio_module = None  # type: ignore[assignment]
    _PYAUDIO_AVAILABLE = False

# pydub availability is checked lazily inside _load_audio()
_PYDUB_AVAILABLE: bool = False
try:
    from pydub import AudioSegment
    _PYDUB_AVAILABLE = True
except ImportError:
    pass

try:
    from performance_engine.modules.shared import say
except ImportError:
    def say(text: str, emoji: str = "") -> None:
        print(f"{emoji} {text}" if emoji else text)

from performance_engine.modules.context import command_registry

# Player class
class AudioPlayer:
    """
    Singleton audio player wrapping PyAudio stream output.
    Loads audio files via pydub (supports MP3, FLAC, WAV,
    OGG, AAC), normalizes them to 16-bit PCM, and streams
    them through PyAudio.
    Playback runs on a background daemon thread so the
    AudioScript shell remains responsive during playback.
    """
    
    def __init__(self):
        self._pa: Optional[object] = None
        self._stream: Optional[object] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_flag: threading.Event = threading.Event()
        self._playing: bool = False
        self._current_file: str = ""
        self._volume: float = 1.0    # 0.0 - 1.0

        self.chunk: int = 1024         # frames
        self.channels: int = 2         # stereo (default)
        self.samplerate: int = 44100   # 44.1 kHz
    
    # Internal helpers
    def _ensure_audio(self) -> None:
        """
        Lazily initialize PyAudio on first use
        """
        if self._pa is None:
            if not _PYAUDIO_AVAILABLE:
                raise RuntimeError(
                    "pyaudio not installed. Run: pip install pyaudio"
                )
            self._pa = _pyaudio_module.PyAudio() # type: ignore[union-attr]
    
    def _load_audio(self, path: str):
        """
        Load an audio file using pydub.
        Supports WAV, MP3, FLAC, OGG, AAC, and any ffmpeg-
        supported format.
        
        Args:
            path: Path to the audio file.
            
        Returns:
            AudioSegment normalized to 16-bit stereo PCM.
            
        Raise:
            RuntimeError: If pydub is not installed.
            FileNotFoundError: If the file does not exist.
        """
        if not _PYDUB_AVAILABLE:
            raise RuntimeError(
                "pydub not installed. Run: pip install pydub\n"
                "Also ensure ffmpeg is installed: sudo apt install ffmpeg"
            )
        
        import os
        from pydub import AudioSegment as _AudioSegment
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Audio file not found: {path}")
        
        # Detect format from extension
        ext = os.path.splitext(path)[1].lower().strip(".")
        if ext in ("mp3",):
            segment = AudioSegment.from_mp3(path)
        elif ext in ("flac",):
            segment = AudioSegment.from_file(path, format="flac")
        elif ext in ("ogg",):
            segment = AudioSegment.from_ogg(path)
        elif ext in ("wav",):
            segment = AudioSegment.from_wav(path)
        else:
            # Fallback - let pydub/ffmpeg figure it out
            segment = AudioSegment.from_file(path)

        # Normalize to 16-bit stereo at configured sample rate
        segment = segment.set_sample_width(2)
        segment = segment.set_channels(self.channels)
        segment = segment.set_frame_rate(self.samplerate)

        return segment
    
    # Public interface
    def play(self, path: str) -> None:
        """
        Play an audio file. Stops any current playback first.
        Loads the file via pydub, normalizes it to PCM, then
        streams it through PyAudio on a background thread.
        
        Args:
            path: Path to the audio file 
                  (WAV, MP3, FLAC, OGG, etc.)
        """
        self._ensure_audio()

        # Stop any existing playback cleanly
        if self._playing:
            self.stop()
            time.sleep(0.1)

        try:
            say(f"[player] Loading: {path}", "📂")
            segment = self._load_audio(path)

            # Apply volume
            if self._volume < 1.0:
                # pydub dB math
                segment = segment + (20 * (self._volume - 1))
            
            raw_data = segment.raw_data
            assert self._pa is not None

            self._stream = self._pa.open(  # type: ignore[union-attr]
                format=_pyaudio_module.paInt16,  # type: ignore[union-attr]
                channels=self.channels,
                rate=self.samplerate,
                output=True,
            )

            self._stop_flag.clear()
            self._playing = True
            self._current_file = path

            say(f"[player] Now playing: {path}", "🔊")

            def _playback_loop():
                offset = 0
                assert self._stream is not None
                while not self._stop_flag.is_set():
                    chunk = raw_data[offset: offset + self.chunk * 4]
                    if not chunk:
                        break
                    self._stream.write(chunk)  # type: ignore[union-attr]
                    offset += self.chunk * 4
                
                # Clean up after playback ends
                self._stream.stop_stream()  # type: ignore[union-attr]
                self._stream.close()  # type: ignore[union-attr]
                self._stream = None
                self._playing = False
                if not self._stop_flag.is_set():
                    say("[player] Playback complete.", "✅")
                
            self._thread = threading.Thread(
                target=_playback_loop, daemon=True
            )
            self._thread.start()
        
        except FileNotFoundError as e:
            say(f"[player] File not found: {e}", "❌")
        except RuntimeError as e:
            say(f"[player] {e}", "❌")
        except Exception as e:
            say(f"[player] Playback error: {e}", "❌")

    def stop(self) -> None:
        """
        Stop current playback immediately.
        """
        if not self._playing:
            say("[player] Nothing is playing.", "⚠️")
            return
        self._stop_flag.set()
        self._playing = False
        say("[player] Playback stopped.", "🔇")

    def set_volume(self, volume: float) -> None:
        """
        Set playback volume.
        
        Args:
            volume: Float between 0.0 (silent) and 1.0 (full)
        """
        self._volume = max(0.0, min(1.0, float(volume)))
        say(f"[player] Volume → {self._volume:.0%}", "🔊")
    
    def status(self) -> None:
        """
        Print current playback state.
        """
        if self._playing:
            say(
                f"[player] Playing: {self._current_file} "
                f"| volume={self._volume:.0%}",
                "🔊"
            )
        else:
            say("[player] Idle - nothing playing.", "💤")

# Singleton instance
_PLAYER: Optional[AudioPlayer] = None

def _player() -> AudioPlayer:
    """
    Return the singleton AudioPlayer, creating it if needed.
    """
    global _PLAYER
    if _PLAYER is None:
        _PLAYER = AudioPlayer()
    return _PLAYER

# AudioScript command functions
def play(*args) -> None:
    """
    Play an audio file.
    
    Args (from AudioScript shell):
        args[0]: Path to audio file (WAV, MP3, FLAC, OGG, etc)
        
    Examples:
        play(track.wav)
        play(my_song.mp3)
    """
    if not args:
        say("[player] Usage: play(filename)", "⚠️")
        return
    path = str(args[0]).strip().strip('"')
    _player().play(path)

def player_stop(*_) -> None:
    """
    Stop current playback.
    """
    _player().stop()

def player_status(*_) -> None:
    """
    Show current playback state.
    """
    _player().status()

def player_volume(*args) -> None:
    """
    Set playback volume.
    0.0 = silence, 1.0 = full volume
    
    Args:
        args[0]: Volume level 0.0 to 1.0
    """
    if not args:
        say("[player] Usage: player.volume(0.0-1.0)", "⚠️")
        return
    _player().set_volume(float(args[0]))

# Registration
def register() -> dict:
    """
    Register audio player commands with the AudioScript
    shell.
    Called automatically by the module loader in
    `audioscript_runtime.py`
    """
    return {
        "play": play,
        "player.stop": player_stop,
        "player.status": player_status,
        "player.volume": player_volume,
    }
