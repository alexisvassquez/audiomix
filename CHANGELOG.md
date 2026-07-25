
# 🎧 AudioMIX Core Engine

## 📦 CHANGELOG

All notable changes to the AudioMIX core engine will be documented in this file.

The AudioMIX Electron UI has its own separate changelog in the [AudioMIX Electron UI repository](https://github.com/alexisvassquez/audiomix-electron).

---

## [v0.8-dev] - 2026-07-25

### Architecture

- FastAPI bridge (`api/main.py`) is now a fully local-first, auth-required entrypoint. No dev-mode bypass exists — the server refuses to start at all if `AUDIOMIX_API_TOKEN` is unset, rather than silently running without auth. This was a deliberate choice: local-first (no cloud hosting, ever) does not mean auth-optional, since a shipped Windows/ Linux build still needs to defend against other processes on a user's own machine.
- Formalized LIVE mode as pause/resume, not start/stop. Entering LIVE mode starts the AudioScript runtime subprocess only once; leaving LIVE mode leaves it running idle in the background rather than killing it, so re-entering later is instant with no state loss. STUDIO mode never needs the runtime running at all.
- Confirmed the intended `enter_live_mode()`/`exit_live_mode()` split as a pure mechanism/policy boundary: the bridge only tracks whether the runtime is alive and routes commands to it; whether commands are allowed to be sent while paused is left to the Electron UI to enforce (e.g. disabling the shell input outside LIVE mode), not the bridge.

### Added

- `api/main.py` — new file. FastAPI entrypoint with:
  - `lifespan` context manager (not the deprecated `@app.on_event`) to guarantee the AudioScript runtime subprocess is terminated on clean shutdown.
  - CORS locked to the confirmed electron-vite dev origin (`localhost:5173` / `127.0.0.1:5173`) plus `file://` for the packaged app.
  - `verify_token()` — per-router `Depends()` auth dependency using `secrets.compare_digest`, replacing an earlier global-middleware draft that silently ran with no auth at all if the token was unset.
  - `/health` — deliberately left public (no `Depends`) so Electron can poll liveness on startup without needing a token first.
- `AudioMIXBridge.enter_live_mode()` / `exit_live_mode()` in `api/bridge.py` — starts the runtime subprocess on first LIVE entry only; exit flips the session back to the IR branch without touching the subprocess.
- `AudioMIXBridge._wait_for_runtime_ready()` — blocks start() until the runtime prints its own `"Welcome to AudioMIX"` banner, closing a race where an early command could receive leftover startup output instead of its own result.
- `POST /shell/live/enter` and `POST /shell/live/exit` routes in `api/routes/shell.py` — token-protected via the existing router-level `Depends(verify_token)`.
- WebSocket-specific token check in `shell.py`'s `/ws` route, since `Depends()` on `include_router` does not cover WebSocket handlers — unauthorized handshakes are now rejected before `accept()` with a custom `4401` close code.
- `electron/shellBridge.js` — new file. Main-process-owned WebSocket client to `/shell/ws`, speaking the `WSMessage` envelope in both directions. Exponential backoff reconnect; sends `x-audiomix-token` as a handshake header.
- `preload.cjs` — added shell key to the existing `exposeInMainWorld` call: `sendCommand`, `isConnected`, `onMessage`, `onStatus`.
- `src/hooks/useShellConnection.js` — new file. Renderer hook dispatching on `WSMessageType` (`session_update`, `shell_output`, `error`, `pong`) rather than treating every message as one undifferentiated blob.
- `.env.example` (both repos) documenting `AUDIOMIX_API_TOKEN`, `AUDIOMIX_API_PORT`, `AUDIOMIX_ENV` — actual `.env` gitignored in both.

### Changed

- `AudioMIXBridge.send_command()` (`api/bridge.py`) — no longer reads `stdout` directly. Response reading now goes through an `asyncio.Queue` fed exclusively by the existing `_read_runtime_output()` background task, plus a pre-send drain of any stale queued lines.

### Fixed

- Resolved `readuntil() called while another coroutine is already waiting for incoming data` — two different coroutines (`send_command()` and the background `_read_runtime_output()` task) were both calling `stdout.readline()` on the same subprocess stream concurrently. `asyncio.StreamReader` only permits one reader at a time.
- **The real goblin of the night:** full (non-safe) mode was taking dramatically longer to boot than safe mode, severe enough to strain WSL2 to the point of crashing it outright, twice.
  - Root cause: `pydub`'s `AudioSegment` import performs an ffmpeg auto-detection scan across every directory in `$PATH` — and this machine's `$PATH` includes a long chain of `/mnt/c/...` Windows paths, each one a slow cross-filesystem 9P call from inside WSL2.
  - Fixed by setting `AudioSegment.converter = "/usr/bin/ffmpeg"` explicitly in `audio_player.py` right after import, so pydub never needs to search `$PATH` at all.
- Rebuilt a stale `.venv` that still carried the pre-rename absolute path (`ai_spotibot_player/.venv` baked into `pyvenv.cfg`) — silently caused `python3`/`pip` to fall through to the system interpreter despite `(.venv)` showing correctly in the shell prompt. Also corrected a matching stale `alias audiomix=...` entry in `~/.bashrc` still pointing at the old folder name.
- Corrected a fake/nonexistent `torchaudio==2.13.0` pin in `requirements.txt` (no such version exists on PyPI, thanks Google 😒) blocking `pip install -r requirements.txt` entirely.
- `pip install pretty_midi` — resolved `midi_bridge.py`'s `No module named 'pretty_midi'` import failure; now registers cleanly alongside every other module in full (non-safe) mode.
- Pylance `reportCallIssue`/`reportArgumentType` on `secrets.compare_digest` in `main.py` — `API_TOKEN` was typed `str | None` even though a `raise` earlier in the module guaranteed it non-empty by the time `verify_token()` read it; fixed by annotating `API_TOKEN: str = os.environ.get(...) or ""` so the type is concrete without changing runtime behavior.

### Notes

- Confirmed end-to-end via `curl`: token rejected without header (401), accepted with valid header, `enter_live_mode()` spins up the runtime exactly once across repeated enter/exit/re-enter cycles (no respawn), and `glow("cyan")` returns its own real result instead of stale runtime startup output.
- Electron-side wiring (`shellBridge.js`, `preload.cjs`, hook) is written and tailored to the real `WSMessage`/token contract, but not yet verified end-to-end against a running Electron instance — next session starts there.
- AS Shell panel UI itself still does not exist. `useShellConnection` is ready to be consumed the moment it does. In development.

---

## [v0.7-dev] - 2026-06-02

### Architecture

- Aligned `session_state.py` with the AudioMIX Electron UI data model.
  `SessionState` is now the single source of truth between the Python
  engine and the Electron renderer — every field maps to a specific UI
  surface and will be serialized over the FastAPI/WebSocket bridge when
  the bridge is implemented.

### Added

- `performance_engine/session_state.py` — major expansion:

  - `ClipLayer` dataclass — models a single audio layer inside a clip
    container. Mirrors the layer data model in `audiomix-layers.jsx`.
    Fields: `id`, `name`, `source_file`, `gain`, `freq_profile` (7-band
    energy array: SUB, BASS, LO MID, MID, HI MID, PRESENCE, AIR).

  - `ClipState` dataclass — models a clip container in the arrangement.
    Clips are containers, not flat blocks — each clip holds multiple
    `ClipLayer` instances that blend together. Mirrors the clip data
    model in `audiomix-layers.jsx`. Fields: `id`, `track_id`, `name`,
    `start_bar`, `length_bars`, `layers`, `is_dragging`.

  - `HALDevice` dataclass — models a connected hardware device.
    HAL covers LED arrays, DMX lighting rigs, MIDI controllers, OSC
    routing, speakers, and connected stage machinery. Fields: `name`,
    `status` ("online" | "offline" | "idle"), `detail`, `device_type`
    ("led" | "midi" | "osc" | "dmx" | "audio").

  - `make_default_session()` — factory function for clean session
    initialization with sensible defaults. Called at AudioMIX boot or
    when a new project is created. Accepts `project_name` argument which
    flows through to the Electron TopBar and StatusBar displays.

  - New `SessionState` fields added with GUI mapping documented inline:

    | Field | GUI Surface |
    | :---- | :---------- |
    | `is_recording` | Transport.jsx record button state |
    | `playhead_bar` | Arrangement playhead position |
    | `project_name` | TopBar.jsx project display |
    | `scene_name` | Sidebar.jsx active scene |
    | `time_signature` | Transport.jsx time signature display |
    | `active_script` | AS Shell panel active script |
    | `audioscript_branch` | Sidebar.jsx IR/Live branch switcher |
    | `last_as_command` | AS Shell console output |
    | `last_as_result` | AS Shell console output |
    | `reverb_mix` | Right panel reverb knob |
    | `compressor_ratio` | Right panel compressor knob |
    | `delay_ms` | Right panel delay knob |
    | `sample_rate` | StatusBar.jsx audio telemetry |
    | `buffer_size` | StatusBar.jsx audio telemetry |
    | `latency_ms` | StatusBar.jsx audio telemetry |
    | `cpu_percent` | StatusBar.jsx CPU display |
    | `active_clips` | Arrangement clip layer model |
    | `hal_devices` | Sidebar HAL devices panel |
    | `last_error` | Debug introspection |

### Notes

- `session_state.py` is now shaped for direct JSON serialization via
  the FastAPI bridge. When the bridge is implemented, `SessionState`
  serializes to the exact JSON structure the Electron renderer expects.
- `ClipLayer.freq_profile` is a 7-band energy array that feeds both
  the frequency view spectrogram and Juniper2.0's clash detection logic.
- All new fields include TODO comments pointing to the specific core
  files that will eventually populate them.
- `HALDevice` replaces the previous raw `Dict[str, Any]` for
  `hal_devices` — typed fields enable proper serialization and
  IDE-assisted development when wiring the HAL layer.

---

## [v0.6-dev] - 2026-05-07

### Architecture

- Defined the two-mode system design that unifies AudioMIX around a clear north star:

  - **Studio Mode** — producer at a desk, AI as collaborator, GUI + live coding, iterative and creative.
  - **Performance Mode** — on stage, AI autonomous, crowd-reactive, real-time DSP adjustments, lights in sync.
  - **AudioScript IR** established as the bridge between modes: authored in Studio, executed and mutated in Performance.

- Identified the missing communication backbone and designed the layered message bus architecture:

  - Python runtime → EventBus → DSPBridge → NDJSON → C++ `controlLoop` → DSP modules.

### Added

- `performance_engine/event_bus.py` — promoted from stub to fully operational pub/sub backbone.
  - Added singleton `bus` instance shared across all of AudioMIX.
  - Added full module docstring documenting the pub/sub philosophy, event naming conventions, and usage examples.

- `performance_engine/dsp_bridge.py` — new file. The communication layer between the Python runtime and the C++ DSP engine.
  - Subscribes to DSP events on the `EventBu`s and serializes them to NDJSON for the C++ `controlLoop`.
  - Handles `dsp.eq.set`, `dsp.compressor.set`, `dsp.gain.set`, and `dsp.ping`.
  - Thread-safe send via `threading.Lock` to prevent interleaved NDJSON on the pipe.
  - `listen_for_acks()` stubbed and shaped for future `subprocess.Popen` integration.
  - `attach_dsp_bridge()` convenience factory for clean startup wiring.

- `performance_engine/modules/compressor.py` — new Python-side command module.
  - Registers `compressor.set`, `compressor.status`, and `compressor.reset` in the AudioScript shell.
  - Full parameter validation with descriptive error messages (threshold, ratio, attack_ms, release_ms).
  - Partial update support — omitted arguments retain their current values.
  - Emits `dsp.compressor.set` to the `EventBus` on every successful set.

- `audio/dsp/core/compressor_params.h` — new C++ struct mirroring Python compressor parameters.
- `audio/dsp/core/compressor_params_parse.h` — new NDJSON parser for compressor.set messages.
  - Partial update aware — missing fields fall back to current `CompressorParams` values rather than hardcoded defaults.

- `audio/dsp/audiomix_dsp.h` — new umbrella header consolidating all DSP core and module includes.
  - Separates interface headers (included) from internal utility headers (pulled in transitively).
  - Adding new DSP modules now requires a single line here rather than touching `main.cpp`.

### Changed

- `main.cpp` — significant cleanup and compressor integration:
  - Replaced individual DSP includes with single `#include "audio/dsp/audiomix_dsp.h"`.
  - Added `CompressorModule*` to `ControlBus` and `AudioState`.
  - Added `compressor.set` handler to `controlLoop` with proper ack and error responses.
  - Wired `CompressorModule` into the DSP chain: Choir → Shimmer → EQ → Compressor → Gain → Clipper.
  - Removed dead code path in `controlLoop` (unreachable `unknown_command` error after `eq.set`).
  - Cleaned stale TODO comments now that NDJSON parsing is real.
  - Clarified PortAudio input/output parameter variable naming to eliminate scope confusion.

- `audioscript_runtime.`py`:
  - Removed duplicate `main()` stub (`reportRedeclaration` fix).
  - Integrated `attach_dsp_bridge()` call at boot, before module loading.
  - Fixed `trigger_zones()` import path: `audio.ai.inference_engine` -> `audio.ai.analysis.inference_engine`.
  - Rewrote `parse_and_execute()` argument splitting — now handles empty args, quoted string args, and comma-separated numeric args correctly as three distinct cases. Fixed shadowed `line` variable in result loop.

- `CMakeLists.txt`:
  - Added `set(CMAKE_EXPORT_COMPILE_COMMANDS ON)` to generate `compile_commands.json` for IntelliSense.
  - Replaced `FetchContent` nlohmann_json with system package (`sudo apt install nlohmann-json3-dev`) — faster, more reliable, no network dependency at configure time.

- `requirements.txt`:
  - Pinned `torch==2.7.1`, `torchaudio==2.7.1`, `torchvision==0.22.1` to resolve binary compatibility conflict that was preventing five performance engine modules from registering.

### Fixed

- Resolved `torchaudio` undefined symbol error (`torch_library_impl`) caused by mismatched `torch`/`torchaudio`/`torchvision` versions.
- Fixed `audio.ai.inference_engine` import path in `led_controller.py` and related modules — corrected to `audio.ai.analysis.inference_engine`. Unblocked registration of `sequencer.py`, `crossfade.py`, `led_controller.py`, `clip_launcher.py`, and `sampler.py`.
- Fixed syntax error in `audience_listener.py` (unmatched `)` on line 40).
- Installed `pretty_midi` in new virtual environment, unblocking `midi_bridge.py` registration.
- Fixed `constainsCmd` typo in `main.cpp` `controlLoop` (was causing C++ compiler error).
- Fixed `param_ids.h` enum syntax — stray semicolon after `GainDb = 0` replaced with comma, resolving five cascading C++ compiler errors.
- Fixed `inputParams` scope error in `main.cpp` PortAudio setup block.
- Resolved VS Code IntelliSense false positives by pointing `c_cpp_properties.json` at `build/compile_commands.json` — IntelliSense now reads directly from the compiler's own configuration.

- `DSPBridge._send()` — added `separators=(',', ':')` to `json.dumps()` to
  remove spaces from serialized NDJSON. Python's default serializer produces
  `"cmd": "compressor.set"` (with spaces) while `containsCmd` in C++ matches
  against `"cmd":"compressor.set"` (no spaces), causing all commands to fall
  through to `unknown_command`. One space character. That was the goblin. 🎯

### Milestone

- First successful end-to-end round-trip confirmed: AudioScript shell command -> `parse_and_execute` -> `compressor_set` -> `bus.emit` -> `DSPBridge._handle_compressor_set` -> NDJSON serialization -> confirmed delivery. All layers of the Python pipeline communicating as designed. 🎛️

- **Phase 1 complete. Full round-trip confirmed with live ack from C++ engine:**
  AudioScript shell → `parse_and_execute` → `compressor_set` → `bus.emit` →
  `DSPBridge` → NDJSON subprocess pipe → `controlLoop` → `CompressorModule.setParams()`
  → `{"cmd":"ack","ack":"compressor.set"}` → `[DSPBridge ← DSP] ack: compressor.set`

  Every layer of the Python ↔ C++ pipeline operational. AudioMIX is now a
  connected system. 🎛️

Boot sequence (all modules now registering cleanly):

```bash
🌉 DSP bridge attached
🧠 shell_tools, audio_recorder, sequencer, audience_listener, audio_player,
   eq, track_engine, crossfade, led_controller, reset, clip_launcher,
   sampler, provider_commands, mood_engine, midi, midi_bridge
```

### Notes

- The C++ process is currently started separately from the Python runtime. `subprocess.Popen` launch from within `DSPBridge` is the next planned integration, which will close the pipe fully and enable real bidirectional ack flow.
- `session_builder.py`, `fade_mod.py`, `context.py`, `mixer_panel.py`, `shared.py` intentionally show `⚠️ No register()` — these are utility stubs not yet promoted to command modules.

---

## [v0.5-dev] - 2026-01-06

### Added

- DSP: Introduced a dedicated DSP modules library (`audiomix_dsp_modules`) with its own CMake subdirectory, enabling scalable module development without modifying `main.cpp` or root source lists.
- DSP: Added `GainModule` with dB-based gain control, linear-domain smoothing via `SmoothedParameter`, and real-time safe per-sample processing.
- DSP: Established a hardened DSP chain foundation designed to scale toward multichannel setups (default target: 4 channels for live and booth-style configurations).

### Changed

- Build: Refactored CMake architecture to clearly separate DSP core and DSP modules, improving dependency hygiene, incremental build times, and long-term maintainability.
- DSP: Aligned module implementations with existing core DSP APIs (e.g., `SmoothedParameter`) to avoid abstraction drift and ensure deterministic startup/reset behavior.

### Fixed

- DSP: Corrected issues in `DelayLine` reset logic and related DSP utilities that could cause compilation or runtime instability.
- Build: Fixed incorrect `file(GLOB ...)` argument ordering in CMake that prevented module `.cpp` files from being discovered.
- Build: Resolved system clock skew and timestamp-related build warnings that could cause unreliable incremental builds.

---

## [v0.4-dev] - 2025-11-06

### Added

- `audio_recorder.py` using PyAudio + ALSA for low-latency microphone capture on Chrom-E
- `record()`, `record_stop()` AudioScript commands for real-time and timed audio takes
- `list_inputs()`, `record_set_input()`, `record_set_format()` for device selection + channel/rate config
- Terminal-based countdown during `oneshot()` recordings
- Cross-verified `.wav` output using `arecord`, `aplay`, `ffplay` CLI tooling
- Support for fallback playback via ChromeOS Files app due to null sink limitation in Crostini

### Changed

- `oneshot()` logic hardened with goblin-proof error handling and CLI feedback
- Recording now defaults to 48000 Hz / mono (safe for Chromebooks + VirtIO)

### Known Limitations

- Playback from within Crostini currently blocked by `null-sink` on non-owner accounts (Chrom-E limitation)
- Recommended workaround: export or play `.wav` files using Chrome browser or host system

---

## [v0.4-dev] - 2025-10-06

### Performance Engine Note

- Added `audience_listener.py` script (live mic input module)
- Detects crowd energy, cheering, or silence based on amplitude thresholds
- Used to influence `mood` and trigger LED zone changes via `trigger_zones()`
- Forms part of the Juniper2.0 reactive loop for stage-aware performances

### Added

- **Functional language features to AudioScript v0.2**:
- `let` expressions for pattern variables and FX chains
- `repeat()`, `take()`, and lazy evaluation for infinite sequences
- `with` operator for chaining FX: `play("beat") with stutter + reverb`
- `dsl_helpers.py` for Haskell-inspired functional utilities
- `runtime_state.py` to track variables, macros, and event hooks
- New `core.py` refactor of the interpreter shell
- CLI-compatible REPL with support for script evaluation and mood-aware shell
- New keywords added to `AudioScript.ebnf` grammar
- Functional-reactive design principles aligned with AudioMIX architecture
- `intro_showcase.audioscript`: official v0.2 demo script showcasing `let`, `repeat()`, `with` chaining, LED FX, and mood triggers

### Changed

- `audioscript_runtime.py` split and refactored into modular runtime components
- AudioScript README updated with new language features and functional DSL architecture
- `AUDIOSCRIPT_SPEC.md` rewritten to document lazy evaluation, chaining, and reactivity

### Fixed

- Improved REPL handling for nested command input and invalid function chains
- Robust fallback in `parse_and_execute` for misused commands
- Emoji-safe REPL output and better formatting of chained outputs

---

## [v0.4-dev] - 2025-10-06

### Performance Engine Note

- Added `audience_listener.py` script (live mic input module)
- Detects crowd energy, cheering, or silence based on amplitude thresholds
- Used to influence `mood` and trigger LED zone changes via `trigger_zones()`
- Forms part of the Juniper2.0 reactive loop for stage-aware performances

### Added

- **Functional language features to AudioScript v0.2**:
- `let` expressions for pattern variables and FX chains
- `repeat()`, `take()`, and lazy evaluation for infinite sequences
- `with` operator for chaining FX: `play("beat") with stutter + reverb`
- `dsl_helpers.py` for Haskell-inspired functional utilities
- `runtime_state.py` to track variables, macros, and event hooks
- New `core.py` refactor of the interpreter shell
- CLI-compatible REPL with support for script evaluation and mood-aware shell
- New keywords added to `AudioScript.ebnf` grammar
- Functional-reactive design principles aligned with AudioMIX architecture
- `intro_showcase.audioscript`: official v0.2 demo script showcasing `let`, `repeat()`, `with` chaining, LED FX, and mood triggers

### Changed

- `audioscript_runtime.py` split and refactored into modular runtime components
- AudioScript README updated with new language features and functional DSL architecture
- `AUDIOSCRIPT_SPEC.md` rewritten to document lazy evaluation, chaining, and reactivity

### Fixed

- Improved REPL handling for nested command input and invalid function chains
- Robust fallback in `parse_and_execute` for misused commands
- Emoji-safe REPL output and better formatting of chained outputs

---

## [v0.4-dev] - 2025-09-24

### Debugging Milestone

- Completed module-by-module registration test with **Ultra-Safe Runtime**:
  - All modules imported cleanly.
  - No runtime kills when loaded individually.
  - Confirmed that `context.py` and `shared.py` are utility-only (no commands).
  - `fade_mod.py` flagged for a future `register()` implementation or conversion to helper-only.
- Verified that **runtime crashes are caused by system memory limits (Chrom-E/Crostini OOM)**, not by logic errors in the AudioScript runtime or modules.
- Introduced **safe mode strategy** (`AUDIOMIX_SAFE=1`) and allowlist-based loading for stability on resource-constrained systems.
- Reassured that overall **project architecture is sound**; AudioMIX shell and modules behave as designed once loaded.

### Notes

- *Chrom-E,* the stalwart Chromebook dev machine, successfully carried both **AudioMIX** and **Track That Money** through this stage of development. 🖤👑  
- **All hail Chrom-E, King of the Chromebooks!** 👑 Long may he reign until his teammate mini-PC arrives.  
- Future work: acquire a dedicated mini-PC teammate for heavier compilation and ML workloads, while Chrom-E continues to serve as a reliable dev/test environment.

---

## [v0.4-dev] - 2025-09-18

Includes backlog of changes previously unaccounted for.

### Added

- `__init__.py` files in `audio_providers/` and `audio_providers/bandcamp/` to treat directories as Python packages and enable clean imports.
- **Lossless/lossy playback A/B**
  - Introduced a runtime playback mode toggle to audition “studio (lossless)” vs “real-world (lossy)” sound.
  - New AudioScript commands: `set_mode("lossless" | "lossy", codec="mp3_128" | "mp3_320" | "aac_256" | "ogg_320" | "opus_160" | "wav" | "flac")` and `get_mode()`.
  - Codec simulation implemented with ffmpeg encode -> decode round-trip to float32 WAV (48 kHz), mirroring actual streaming playback.
- **Codec helpers:** Added `audio/utils/codec_sim.py` with:
  - `roundtrip_lossy()` for encode/decode
- Extended converter to normalize any input (WAV/AIFF/FLAC/MP3/AAC/OGG/OPUS) to stereo, 48 kHz, float32 WAV for consistent analysis/playback.
- Looping support to `clip_launcher.py` for EDM/beat-making workflows.
- Expanded **Sampler** module:
  - Sampler bank loading with aliases + attribution (Freesound CC-BY, etc.)
  - Playback of samples via `sampler.play`
  - Console/show credits export for attribution.
- MIDI integration improvements:
  - `midi.py` — quantized real-time MIDI listener with `midi_map`, `midi_tick`, and clock handling.
  - `midi_bridge.py` — mapping JSON loader and tag-classification pipeline to AudioScript actions.

### Changed

- Renamed `spotify/` directory to `audio_providers/` to support Spotify and Bandcamp integrations.
- Cleaned absolute imports and typos across `sampler.py`, `midi.py`, and `midi_bridge.py`.

### Fixed

- Safer temp-file lifecycle around transcoding and simulation artifacts
- Cleanup after playback.
- Clearer errors when `ffmpeg` is not found (actionable message instead of silent failure).

### Debugging / Refactor

- Began major debugging phase of the **AudioScript Runtime** (`audioscript_runtime.py`):
  - Fixed relative import errors across multiple modules.
  - Added `register_command()` helper to cleanly register runtime commands.
  - Corrected `command_registry("...")` misuse -> proper registration calls.
  - Updated command parser to unpack arguments correctly with `*parts`.
  - Fixed variable typos (e.g., `wav_pth` -> `wav_path`) in playback function.
- Refactored **Clip Launcher** (`clip_launcher.py`):
  - Removed `sounddevice` dependency (To keep Chrom-E safe).
  - Implemented `aplay`-based fallback for audio playback.
  - Fixed retrigger logic, choke group handling, and typo bugs (`_PLAYERS[name] - pl` → `_PLAYERS[name] = pl`).
- Cleaned up **provider API** (`provider_api.py`):
  - Converted abstract method stubs to `...` to avoid indentation errors.
  - Fixed registry reference typo (`registry` -> `_registry`).
- Began auditing runtime imports for excessive top-level weight:
  - Identified heavy AI/audio imports (librosa, transformers, etc.) as a likely source of `Killed` errors on low-memory systems.
  - Planned lazy-import strategy and safe-mode module loading.
- Updated `requirements.txt`:
  - Removed `sounddevice`.
  - Marked other heavy libs as candidates for optional/deferred use.

### TODO

- **AS Shell stability:** remove any unnecessary imports at the top-level and spread them out to fix what's causing crashes.

---

## [v0.3.3-dev] – 2025-08-06

### Added

- MIDI Feature Extraction Module (`extract_midi_features.py`)
- Genre Tag Classifier (`midi_tag_classifier.py`) with refined tag logic
- Tag-to-Behavior Mapper (`tag_to_settings.py`) with EQ and lighting scene automation
- Integrated EQ preset logic via `eq_preset()` call in `eq_commands.py`
- Created tag-based lighting and mood map (`tag_map.json`) with artistic preset names
- Began tagging system that informs Juniper2.0 performance behavior and AudioScript logic

### Updated

- Expanded tag support to include `modern_pop`, `electronic_dance`, and `classical_expressive`
- Confirmed system prints intelligent, stylized CLI output for user-facing feedback

### Notes

- Emotional + creative states now reflected in automated system response

---

## [0.3.2] - 2025-08-02

### Added

- **PyTorch EQ Model Inference**:
  - Implemented `predict_eq.py` to load `eq_model.pt` and extract features.
  - Predicted multi-label EQ tags with confidence scores from `.wav` and `.mp3` files.
  - Added CLI support for individual file prediction.

- **Auto-EQ Application Pipeline**:
  - Enhanced `predict_and_apply_eq.py` to apply predicted EQ presets to input files.
  - Integrated dynamic preset loading with fallback warnings for unknown tags.
  - Generated matching `.audioscript` files for downstream AudioScript processing.

- **New Presets for Bass Enthusiasts**:
  - Added `"bass_plus"` and `"super_bass"` EQ profiles for enhanced low-end emphasis.
  - Improved label detection to match model output with available presets.

- **Waveform JSON Export Tool**:
  - Introduced `waveform_to_json.py` in `dev_tools/`.
  - Downsamples audio waveforms to 1000-point JSON arrays.
  - Supports waveform duration, samplerate, and amplitude-normalized points.
  - Includes `--markers` CLI flag for custom loop timestamps (e.g., `--markers "intro=0,drop=25"`).

- **Audio Format Auto-Conversion**:
  - Auto-converts `.mp3`, `.m4a`, and `.aac` to `.wav` using `pydub` + `ffmpeg`.
  - Ensures consistent waveform output and compatibility with `soundfile`.

### Fixed

- Fixed `ModuleNotFoundError` for `predict_eq.py` by using `-m` execution (`python3 -m audio.ai.modules.predict_eq`).
- Resolved `NameError` and `TypeError` in `waveform_to_json.py` caused by variable mismatches and data type goblins (e.g., list vs dict).

### Misc

- Added `dev_tools/` directory for safe, shell-free developer utilities.
- Laid groundwork for future MIDI parsing and live waveform visualization in AudioScript shell.

---

## [0.3.1] - 2025-07-27

### Added

- `train_eq_model.py`: Complete EQ model training pipeline using precomputed audio features and EQ label annotations.
- `flatten_features()` method to dynamically flatten all relevant audio feature structures.
- Debug logging for label/feature key matching, sample count, and input shape diagnostics.

### Fixed

- Feature-label mismatch errors due to structural assumptions.
- AttributeError caused by missing `flatten_features()` method in `EQDataset`.
- Deprecation warnings and formatting issues in `analyze_audio.py` related to `tempo` parsing.
- Overwriting issue in `audio_features.json` — now supports append-and-merge logic for multiple sample feature entries.

### Notes

- EQ model now successfully loads features from `audio/analysis_output/data/audio_features.json` and labels from `eq_labels.json`.
- Current state: **Model training confirmed working. Still in test mode.**

---

## [0.3.1] – 2025-07-23

### Added

- New `Ethical API Use` section in README.md outlining responsible, non-scraping interaction with the Spotify Web API.
- Added working `spotify/diagnostic.py` test script for initial Spotify API integration.

### Changed

- Renamed `extract_spotify_features.py` to `spotify_api_features.py` for clarity and better alignment with project goals.

### Notes

- This update reinforces the project's commitment to API transparency, ethical data use, and support for artist integrity.

---

## [0.3.1] - 2025-07-22

### Added

- `train_eq_model.py` script to train a Lightning PyTorch model for EQ classification
- `LightningEQNet` model with support for multi-label output: `bass_boost`, `mids_cut`, `treble`
- `EQDataset` with MFCC + Spectral Contrast feature extraction via `librosa`
- `predict_eq.py` script to infer EQ tags from new `.wav` or `.mp3` files
- Saved model checkpoint at `models/eq_model.pt` and class labels in `models/eq_labels.txt`

### Notes

- First successful end-to-end ML flow: custom audio → features → model training → prediction
- EQ predictions are fully aligned with expected outputs (0.99–1.00 confidence for trained tags)
- No GPU required; model trains and runs inference entirely on CPU inside Chromebook CLI
- Began adding Spotify integration with `extract_spotify_features.py` for model training, but ran into some 403 goblins due to CA certificate mismatch on Crostini. Will need to run from GCP.

---

## [v0.3.0] - 2025-07-20

### Added

- Implemented `eq_dataset.py` to dynamically load features and label EQ presets from audio directory and combined JSON
- Built and debugged `plot_eq_presets.py` for visualizing EQ profiles using matplotlib, with smart parsing of both dict and list formats
- Added support for color-coded line plots, log-scaled frequency axes, and auto-saving plots to `docs/plots/`
- Integrated debug print logs and validation checks for preset data integrity
- Created `lightning_module.py` using PyTorch Lightning for training models to infer EQ presets from MFCC + spectral contrast
- Linked `presets_combined.json` as unified preset source
- Synced local environment with GCP (Google Cloud Platform), created multi-region storage bucket for AudioMIX training data
- `version.py` to keep track of version control via CLI

### Changed

- Updated plotting script to parse `gain_db` instead of `gain` field
- Reorganized project tree and confirmed compatibility with GCP CLI utilities

### Fixed

- Multiple goblins involving invalid filter structures, empty presets, and incorrect JSON parsing during plotting

---

## [v0.2.2] - 2025-07-14

### Added

- Modular command loader via `load_dynamic_commands()` in `shell_tools.py`
- `fade_mod` command as proof-of-concept for dynamic CLI modules

### Fixed

- Resolved circular import issues by moving `say()` to `utils/shell_output.py`
- Normalized command parsing to pass arguments as list to `run(args)`

---

## [v0.2.1] - 2025-07-05

### Added

- `color(color)` AudioScript command to set static LED color
- `fade(color, duration)` command for LED fade transitions
- `delay(seconds)` command for pausing scripts
- `set_zone(zone)` command for targeting LED regions
- Persistent command history saved to `~/.audioscript_history`
- Arrow key support via `readline` for CLI shell editing

### Changed

- Refactored `shell_tools.py` to instantiate `LightController` properly
- Updated LED command feedback with zone-aware output and emojis
- Improved developer experience for AudioScript Shell CLI

### Fixed

- Resolved `ImportError` when accessing LED controller methods inside class

---

## [v0.2-dev] - 2025-06-26

### Added

- `track_engine.py`: foundational `Track` class with volume, mute, and clip storage
- `crossfade.py`: threaded volume crossfader between tracks with real-time feedback
- AudioScript commands: `add_track()`, `add_clip()`, `set_volume()`, `mute_track()`, `crossfade()`
- ASCII VU meter output in shell reflecting real-time track volumes
- LED pulse logic tied to dominant track volume, scaled 60–200 BPM
- Juniper2.0 shell narration for transitions and system feedback (`say()`)
- Shell visual enhancements: emoji support, LED logs, mood context logs
- `pcvoice.mp3` (moved to `interface/`): original Spotibot voice now canonized as Juniper2.0's audio intro
- `sampler.py`: AudioScript-based sample trigger engine with `load_sample()` and `trigger_sample()`
- Real-time LED pulse feedback when triggering samples
- Support for PCM `.wav` file playback via `aplay`
- Logging of sample playback metadata (bitrate, channels, frequency)
- `sequencer.py`: Step-based pattern engine with `define_pattern()` and `play_pattern()` commands
- AudioScript DSL support for BPM-controlled sample sequencing
- Multi-threaded playback with internal `sequence_loop()` logic
- Real-time LED pulses and PCM playback for each active step
- CLI-safe pattern parsing via `shlex` for string-encoded step sequences

### Changed

- Refactored shell logging to route through `say()` for consistent emoji-based output
- Updated `pulseaudio_oss.sh` for modern Crostini compatibility

### Fixed

- Casted BPM string argument to `float()` inside `play_pattern()` to prevent type errors
- Updated `parse_and_execute()` in `audioscript_runtime.py` to use `shlex.split()` for safe comma handling in string arguments
- Git move/restore issue with legacy Spotibot files
- PulseAudio environment handling under non-owner ChromeOS user accounts

---

## [v0.2-dev] - 2025-05-13

### Added

- `led/` and `led-service/` modules for mood-to-RGB control and CLI-triggerable LED response
- `main.py` in `led-service` to accept JSON input (e.g., `{ "mood": "hype", "bpm": 135 }`)
- Custom color profile mappings and animation patterns (strobe, fade, pulse)
- Mood classification output now returns a full JSON object for downstream integration
- `ETHICAL_AI_MANIFESTO.md` — AudioMIX ethical design and AI principles
- Updated `README.md` to include:
  - JSON-based mood engine
  - Live performance engine reference
  - Ethical AI section

### Changed

- Improved project language to reflect real-time modular architecture
- Replaced “small and simple” messaging with “Modular, expressive, and built for real-time creative performance.”

### Fixed

- Cleaned Git references and removed hardcoded API secrets from committed files
- Regenerated and secured Spotify API credentials; `.env` pattern recommended

---

## [v0.1-alpha] - 2025-04-20

### Added

- `analyze_audio.py` with MFCC, spectral contrast, and BPM analysis
- Initial `main.cpp` and `audio_utils.cpp` for C++ PortAudio integration
- `initial-script.py` prototype and CMake configuration for dual-language build
- Spotibot LED + mood mapping draft
- First public repo structure and commit

---

Future releases will include:

- AudioScript DSL for user-programmable logic
- Arduino LED integration layer
- System map + visual architecture
- Artist-facing UI and Electron/Flask-based interaction layer








