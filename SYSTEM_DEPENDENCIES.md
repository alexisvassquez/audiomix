# AudioMIX – System Dependencies

AudioMIX is a hybrid Python + native audio platform.
The following system-level dependencies must be installed
before installing Python requirements.

---

## Build Toolchain

- CMake >= 3.22
- C++17-compatible compiler
  - gcc/g++ (Linux)
  - clang (macOS)
  - MSVC (Windows)

---

## Audio Stack

- PortAudio (required)
- ALSA (Linux)
- PulseAudio or PipeWire (recommended on Linux)

---

## MIDI Support

- System MIDI backend (ALSA MIDI / CoreMIDI / Windows MIDI)

---

## Python

- Python >= 3.11
- pip
- python3-venv (Debian/Ubuntu)

---

## Notes

Many Python audio packages (PyAudio, sounddevice, pyalsaaudio)
are thin bindings over system libraries. If these system
dependencies are missing, pip installation may succeed
but runtime audio I/O will fail.

## WSL Audio Note

### ALSA has no default device in WSL2

WSL2 has no real ALSA sound card - `aplay` and any ALSA-backed playback (including `clip_launcher.py`'s use of `aplay`) will fail outright with something like:

```bash
ALSA lib confmisc.c:855:(parse_card) cannot find card '0'
ALSA lib pcm.c:2721:(snd_pcm_open_noupdate) Unknown PCM default
aplay: main:834: audio open error: No such file or directory
```

This has nothing to do with PortAudio's build config below - it's a layer underneath that. ALSA needs to be pointed at PulseAudio (which WSLg exposes via a socket) as its default device. Fix by creating `~/.asoundrc` with:

```bash
pcm.!default {
  type pulse
}
ctl.!default {
  type pulse
}
```

Verify with `aplay <any .wav file>` directly before assuming an AudioMIX-side bug if sound isn't coming out - `clip_launcher.py` makes the exact same `aplay` call under the hood, so if it fails standalone it will fail identically from inside the application.

### PortAudio PulseAudio backend

The system PortAudio package does not include PulseAudio backend support.
Build from source before compiling AudioMIX:

```bash
git clone <https://github.com/PortAudio/portaudio.git>
cd portaudio
./configure --with-jack=no --enable-pa-backend-pulseaudio
make -j$(nproc) && sudo make install && sudo ldconfig
```

Then configure AudioMIX with:

```bash
cmake -S . -B build -DPORTAUDIO_ROOT=/usr/local
```
