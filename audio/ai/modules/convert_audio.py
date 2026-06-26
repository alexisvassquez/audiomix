# audiomix
# AudioMIX
# audio/ai/modules/convert_audio.py

# Converts any input audio file to a standard internal
#  format: stereo, float32 WAV at a target sample rate
#  (default 48000 Hz).

from __future__ import annotations
from pydub import AudioSegment
import os, subprocess, shutil, tempfile

def convert_to_wav(input_path):
    """
    Convert any input audio file to a standard WAV format (stereo, 44100 Hz) using pydub.
    """
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(44100).set_channels(2).normalize()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
        audio.export(temp_wav.name, format="wav")
        return temp_wav.name

def _ffmpeg() -> str:
    """
    Find ffmpeg in the system path. 
    Raises an error if not found.
    """
    path = shutil.which("ffmpeg")
    if not path:
        raise RuntimeError("ffmpeg not found. Install it to enable codec.")
    return path

# Convert any input to internal standard: stereo, float32 wav @ target_sr
# Any input includes mp3, m4a, flac, wav, aif, ogg, etc etc etc.
# Returns path to converted wav
def to_internal_wav32f(in_path: str, target_sr: int = 4800) -> str:
    """
    Convert any input audio file to a standard internal WAV format (stereo, float32, target sample rate) using ffmpeg.
    """
    ff = _ffmpeg()
    fd, out_wav = tempfile.mkstemp(prefix="amx_wav_", suffix=".wav")
    os.close(fd)
    cmd = [
        ff, "-y", "-i", in_path,
        "-vn", "-acodec", "pcm_f32le", "-ar", str(target_sr), "-ac", "2",
        out_wav
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_wav

# Always funnel through ffmpeg bc it is fast enough and robust
# No-op if already WAV32F@target_sr stereo; else converts.
def ensure_internal(in_path: str, target_sr: int = 48000) -> str:
    """
    Ensure the input audio file is in the internal standard format (stereo, float32 WAV at target sample rate).
    """
    return to_internal_wav32f(in_path, target_sr)
