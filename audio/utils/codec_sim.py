# audiomix
# AudioMIX
# audio/utils/codec_sim.py

from __future__ import annotations
import os, tempfile, subprocess, shutil
from typing import Tuple

# Supported short codes
# Passthrough (lossless container)
CODEC_MAP = {
    "wav": ("wav", []),
    "flac": ("flac", ["-compression_level", "5"]),
    "mp3_128": ("mp3", ["-b:a", "128k"]),
    "mp3_320": ("mp3", ["-b:a", "320k"]),
    "aac_256": ("m4a", ["-c:a", "aac", "-b:a", "256k"]),
    "ogg_320": ("ogg", ["-c:a", "libvorbis", "-q:a", "8"]),
    "opus_160": ("opus", ["-c:a", "libopus", "-b:a", "160k"]),
}

def ensure_ffmpeg_available() -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not in PATH.")

def parse_codec(codec_key: str) -> Tuple[str, list]:
    if codec_key not in CODEC_MAP:
        raise ValueError(f"Unsupported codec '{codec_key}'. Supported: {', '.join(CODEC_MAP.keys())}")
    return CODEC_MAP[codec_key]

# Transcode input file into the given codec (encode).
# Returns path to the encoded file.
def transcode_once(in_path: str, codec_key: str) -> str:
    ensure_ffmpeg_available()
    container, codec_args = parse_codec(codec_key)
    base = os.path.splitext(os.path.basename(in_path))[0]
    fd, out_path = tempfile.mkstemp(prefix=f"amx_enc_{base}_", suffix=f".{container}")
    os.close(fd)
    cmd = ["ffmpeg", "-y", "-i", in_path, *codec_args, out_path]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path

# Simulates a 'streaming decode' that the listener hears
# Encode + decode back to float32 WAV @ target_sr.
# Returns path to decoded WAV.
def roundtrip_lossy(in_path: str, codec_key: str, target_sr: int = 4800):
    ensure_ffmpeg_available()
    enc_path = transcode_once(in_path, codec_key)
    fd, dec_path = tempfile.mkstemp(prefix="amx_dec_", suffix=".wav")
    os.close(fd)
    # decode to float32 PCM WAV at target_sr (internal AMX standard)
    cmd = [
        "ffmpeg", "-y", "-i", enc_path,
        "-vn", "-acodec", "pcm_f32le", "-ar", str(target_sr), "-ac", "2",
        dec_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Clean the encoded temp artifact
    # keep only the decoded result for playback
    try:
        os.remove(enc_path)
    except OSError:
        pass
    return dec_path
