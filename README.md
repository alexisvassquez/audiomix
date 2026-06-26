# AudioMIX

**AI-assisted music production and live performance — one platform for the studio and the stage.**

![License](https://img.shields.io/badge/license-GPLv3-blue)
![Stack](https://img.shields.io/badge/stack-Python%20%7C%20C%2B%2B%20%7C%20CMake%20%7C%20AudioScript-purple)
![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows-blue)
![Status](https://img.shields.io/badge/status-active%20development-brightgreen)
![AI](https://img.shields.io/badge/AI-powered-orange)
![DSP](https://img.shields.io/badge/audio-DSP-critical)
![Built For](https://img.shields.io/badge/built%20for-artists%20%26%20developers-ff69b4)

> Write a script. Make a beat. Light up a room.

**AudioMIX** is an open-source DAW and live-performance engine for independent artists and developer-musicians. It combines a real-time **C++ DSP** stack, an AI creative layer (**Juniper2.0**), and **AudioScript** — a domain-specific language for controlling audio, mood, lighting, and show logic in code.

This repository is the **core engine**. The desktop UI lives in a separate repo: [AudioMIX-Electron](https://github.com/alexisvassquez/audiomix-electron).

---

## Table of contents

- [Why AudioMIX](#why-audiomix)
- [Quick start](#quick-start)
- [Core features](#core-features)
- [Architecture](#architecture)
- [Project layout](#project-layout)
- [AudioScript](#audioscript)
- [Juniper2.0](#juniper20)
- [External services](#external-services)
- [AudioMIX-Electron](#audiomix-electron)
- [Development](#development)
- [Ethical AI](#ethical-ai)
- [License](#license)

---

## Why AudioMIX

Most DAWs are built for the studio. Most live-coding tools are not built for performers. AudioMIX bridges that gap.

| You are… | AudioMIX gives you… |
| ---------- | --------------------- |
| **Producer** | DSP, mood/ML analysis, EQ tooling, and AI-assisted production workflows |
| **Live performer** | AudioScript to script audio, lighting, and transitions in real time |
| **Developer-musician** | Modular Python/C++ extension points, a compiler pipeline, and an event-driven runtime |

---

## Quick start

### Prerequisites

- **Python 3.11** (recommended; see `requirements.txt` — librosa targets ≤ 3.11)
- **CMake 3.10+**
- System audio: PortAudio and/or PulseAudio, ALSA (Linux)
- Build tools: `build-essential`, `ffmpeg`

Optional: run `./install.sh` on Debian/Ubuntu for system packages and a local `amenv` virtualenv.

### Install and build

```bash
git clone https://github.com/alexisvassquez/audiomix.git
cd audiomix

python3 -m venv amenv && source amenv/bin/activate
pip install -r requirements.txt

cmake -S . -B build
cmake --build build -j"$(nproc)"
```

Verify the DSP build:

```bash
./build/test_sine_dsp
```

### Run the AudioScript shell

```bash
python audioscript_runtime.py
```

Run a script file:

```bash
python audioscript_runtime.py path/to/show.audioscript
# or
python audioscript_runtime.py path/to/show.as
```

Useful flags:

| Flag | Effect |
| ------ | -------- |
| `--safe` | Restrict loaded modules; no hardware/audio side effects |
| `--no-dsp` | Skip launching the C++ `audiomix` binary |
| `--debug` | Verbose module loading |
| `--no-emoji` | Plain text output |

Set `AUDIOMIX_SAFE=1` in the environment for the same allowlist as `--safe`.

### Compile audio → AudioScript (IR)

```bash
python audioscript/compiler/run.py --file your_track.wav
python audioscript/compiler/run.py --file your_track.wav --save
```

---

## Core features

- **Real-time DSP** — C++ engine with EQ, compression, gain, and more (`audio/dsp/`)
- **AudioScript** — Live shell + IR compiler for scripted performances (`audioscript/`)
- **AI / ML analysis** — Mood tagging, MFCC/spectral features, tempo and beat tracking (`audio/ai/`)
- **Performance engine** — Modular command registry, session state, event bus, DSP bridge (`performance_engine/`)
- **Streaming integrations** — Official Spotify Web API; Bandcamp embed support (`audio_providers/`)
- **LED & lighting** — Mood/BPM-driven patterns and reactive output (`audio/led/`, `audio/led-service/`)
- **Audience listener** — Crowd-reactive performance hooks (in development)

---

## Architecture

AudioMIX is organized around two creative modes:

| Mode | Context | Role of AudioScript |
|------|---------|---------------------|
| **Studio** | Desk, iteration, AI as collaborator | Author and refine scripts; use the compiler and analysis pipeline |
| **Performance** | Stage, low latency, crowd-reactive | Execute Live scripts; runtime mutates mood, DSP, and lighting via the event bus |

**Runtime data flow (simplified):**

```bash
AudioScript shell  →  command modules  →  EventBus  →  DSPBridge (NDJSON)  →  C++ audiomix
                              ↓
                        audio/ai, LED, providers
```

![AudioMIX system map](docs/system_map.png)

Full directory snapshot: [`docs/AudioMIX_project_tree.txt`](docs/AudioMIX_project_tree.txt)

---

## Project layout

| Path | Purpose |
| ------ | --------- |
| [`audio/dsp/`](audio/dsp/) | C++ real-time DSP modules and tests |
| [`audio/ai/`](audio/ai/) | ML inference, feature extraction, datasets, planners |
| [`audio/eq/`](audio/eq/) | EQ engine, presets, live streaming |
| [`audio/led/`](audio/led/) | LED controller, color profiles, reactive logic |
| [`audio/led-service/`](audio/led-service/) | FastAPI microservice for mood/BPM JSON input |
| [`performance_engine/`](performance_engine/) | Live runtime: modules, event bus, DSP bridge, session state |
| [`audioscript/`](audioscript/) | Language spec, EBNF grammars, compiler, example scripts |
| [`audio_providers/`](audio_providers/) | Spotify and Bandcamp adapters |
| [`runtime/`](runtime/) | Refactored shell components (see `audioscript_runtime.py` for the current entry point) |
| [`audioscript_runtime.py`](audioscript_runtime.py) | **Primary** interactive AudioScript shell |

Datasets and training metadata live under [`audio/ai/datasets/`](audio/ai/datasets/) (not a top-level `datasets/` folder).

---

## AudioScript

**AudioScript (AS)** is AudioMIX’s musical programming language — human-readable, whitespace-sensitive, and built for emotional, mood-aware control of audio and lighting.

### Live vs IR

| Branch | Use case |
|--------|----------|
| **Live** | Written on stage; forgiving, expressive syntax ([`audioscript/live/`](audioscript/live/)) |
| **IR** | Machine-generated, precise pipelines; compiler output ([`audioscript/ir/`](audioscript/ir/)) |

### Example

```python
mood.set("uplifted")
glow("lilac")
play("intro.wav")
pulse("yellow", bpm=120)
```

### Learn more

- [Language specification](audioscript/AUDIOSCRIPT_SPEC.md)
- [AudioScript directory guide](audioscript/README.md)
- Example scripts: [`audioscript/scripts/`](audioscript/scripts/)

---

## Juniper2.0

**Juniper2.0** is the AI layer built for AudioMIX — not a generic chatbot, but a collaborator that understands AudioScript, mood mappings, LED profiles, and your session context.

- **AudioScript** — Generate and debug Live and IR scripts from natural language
- **Production** — EQ suggestions, track flow, and emotional arc analysis
- **Lighting** — Map inferred mood to color and pattern profiles
- **Live performance** — Audience-aware transitions and guidance (roadmap)

**Design principle:** amplify creative intent; every suggestion is traceable and overridable.

> *"Juniper doesn't replace the artist — she collaborates with them."*

Integration into the CLI and [AudioMIX-Electron](https://github.com/alexisvassquez/audiomix-electron) is in active development.

---

## External services

### Spotify

- Uses the **official [Spotify Web API](https://developer.spotify.com/documentation/web-api)** with OAuth — no scraping
- Feature extraction via permitted endpoints per [Spotify Developer Terms](https://developer.spotify.com/terms)
- Credentials via `.env` (see `.gitignore`; never commit secrets)

### Bandcamp

- Embed-based integration for ethical, artist-facing playback links

---

## AudioMIX-Electron

Companion desktop UI for the core engine — Electron shell with DAW-style panels (mixer, EQ, LED zones) and a secure preload bridge to the Python/C++ backend.

| Layer | Repository |
|-------|------------|
| Core engine | [audiomix](https://github.com/alexisvassquez/audiomix) (this repo) |
| Desktop UI | [audiomix-electron](https://github.com/alexisvassquez/audiomix-electron) |

```bash
git clone https://github.com/alexisvassquez/audiomix-electron.git
cd audiomix-electron
npm install
npm run dev
```

Status: **First Breath** milestone (v0.1-dev). FastAPI bridge to the backend is planned.

---

## Development

### Python stack

Key dependencies (full list in [`requirements.txt`](requirements.txt)):

- Audio: `librosa`, `soundfile`, `sounddevice`, `PyAudio`, `mido`, `python-rtmidi`
- ML: `scikit-learn`, `torch`, `transformers`
- Integrations: `spotipy`
- UX: `rich`

### C++ targets

After `cmake --build build`:

| Target | Role |
| -------- | ------ |
| `audiomix` | Main DSP binary (used by `DSPBridge`) |
| `test_sine_dsp` | Sanity check tone generator |
| `test_clipper` | Clipper module test |

### Contributing

1. Read [`CHANGELOG.md`](CHANGELOG.md) for recent architectural decisions
2. Follow the [Ethical AI manifesto](ETHICAL_AI_MANIFESTO.md)
3. Prefer extending `performance_engine/modules/` and emitting events on `performance_engine.event_bus.bus`

---

## Ethical AI

AudioMIX is developed with an artist-first, emotionally-aware, open-source philosophy.

See **[ETHICAL_AI_MANIFESTO.md](ETHICAL_AI_MANIFESTO.md)** for principles and creative mission.

---

## License

[GNU General Public License v3](LICENSE.txt) — free for independent artists and developers.

---

© 2026 Alexis M. Vasquez · [AMV Digital Studios](https://github.com/alexisvassquez)
