// audiomix
// AudioMIX
// main.cpp

#include <iostream>
#include <vector>
#include <portaudio.h>
#include <thread>
#include <chrono>
#include <cstring>
#include <atomic>
#include <string>
#include <mutex>

// DSP Core + Modules
#include "main.h"
// umbrella DSP header (see below)
#include "audio/dsp/audiomix_dsp.h"

using namespace audiomix::dsp;

/* 
  ControlBus:
  Shared state between the control thread
  and the audio thread.
  The control thread writes parameters
  DSP modules apply them safely
*/
struct ControlBus {
    // Pointer to the EQ module inside DSP chain
    EqModule* eq = nullptr;
    CompressorModule* compressor = nullptr;

    // latest raw EQ command line received
    // control thread writes under mutex; audio thread copies when signaled
    std::mutex pendingMutex;
    EqParams pendingEqParams;
    std::atomic<bool> hasPendingEqParams{false};
    std::atomic<bool> running{true};
};

/*
  AudioState:
  Owns the DSP chain and all per-block
  processing buffers.
*/
struct AudioState {
    DspChain chain;
    // 44.1 kHz
    double sampleRate = 44100.0;
    // 512 samples max buffer size
    unsigned int maxBlockSize = 512;

    // reference module ptrs
    EqModule* eq = nullptr;
    GainModule* gain = nullptr;
    ClipperModule* clipper = nullptr;
    CompressorModule* compressor = nullptr;
    AscensionReverbModule* reverb = nullptr;

    // control plane hook
    ControlBus* control = nullptr;

    std::vector<float> inL, inR;
    std::vector<float> outL, outR;
};

// Helpers
static inline bool containsCmd(const std::string& line, const char* cmd) {
    // simple match for: "cmd":"<cmd>"
    const std::string needle = std::string("\"cmd\":\"") + cmd + "\"";
    return line.find(needle) != std::string::npos;
}

/*
  Control Loop:
  Reads NDJSON commands from stdin and dispatches to DSP
  modules.
  Runs on a dedicated thread, never touches the audio callback.*/
static void controlLoop(ControlBus* bus) {
    std::string line;
    while (bus->running.load(std::memory_order_relaxed) && std::getline(std::cin, line)) {
        if (line.empty()) continue;

        // TEMP DEBUG
        std::cerr << "[controlLoop] received: " << line << std::endl;

        // ping/pong
        if (containsCmd(line, "ping")) {
            std::cout << "{\"cmd\":\"pong\"}" << std::endl;
            continue;
        }

        // Apply EQ from the control thread (off audio thread)
        // eq.set
        if (containsCmd(line, "eq.set")) {
            EqParams parsed;
            if (!parseEqSetLine(line, parsed)) {
                // parse JSON
                std::cout << "{\"cmd\":\"error\",\"error\":\"bad_eq_payload\"}" << std::endl;
                continue;
            }
            // smooth ms
            if (bus->eq) bus->eq->setParams(parsed, 10.0f);
            {
                std::lock_guard<std::mutex> lock(bus->pendingMutex);
                bus->pendingEqParams = parsed;
            }
            bus->hasPendingEqParams.store(true, std::memory_order_release);
            // ack instead of silence (for testing purposes)
            std::cout << "{\"cmd\":\"ack\",\"ack\":\"eq.set\"}" << std::endl;
            continue;
        }

        // compressor.set
        if (containsCmd(line, "compressor.set")) {
            CompressorParams parsed;
            if (!parseCompressorSetLine(line, parsed)) {
                std::cout << "{\"cmd\":\"error\",\"error\":\"bad_compressor_payload\"}" << std::endl;
                continue;
            }
            if (bus->compressor) bus->compressor->setParams(parsed);
            std::cout << "{\"cmd\":\"ack\",\"ack\":\"compressor.set\"}" << std::endl;
            continue;
        }

        // unknown command
        std::cout << "{\"cmd\":\"error\",\"error\":\"unknown_command\"}" << std::endl;
    }
}

/*
  PortAudio Callback
  Runs on the audio thread;
  no allocation, no blocking, no I/O
*/
static int audioCallback(const void* inputBuffer, void* outputBuffer, unsigned long framesPerBuffer, const PaStreamCallbackTimeInfo*, PaStreamCallbackFlags, void* userData) {
    auto* state = static_cast<AudioState*>(userData);
    const float* in = static_cast<const float*>(inputBuffer);
    float* out      = static_cast<float*>(outputBuffer);

    if (!state || !out) return paContinue;

    // guard if PortAudio gives larger block
    if (framesPerBuffer > state->maxBlockSize) {
        std::fill(out, out + (2 * framesPerBuffer), 0.0f);
        return paContinue;
    }

    // Deinterleave input into planar buffers (if present)
    if (in) {
        for (unsigned long i = 0; i < framesPerBuffer; ++i) {
            state->inL[i] = in[2 * i + 0];
            state->inR[i] = in[2 * i + 1];
        }
    } else {
        // input missing => silence
        std::fill(state->inL.begin(), state->inL.begin() + framesPerBuffer, 0.0f);
        std::fill(state->inR.begin(), state->inR.begin() + framesPerBuffer, 0.0f);
    }

    // Process through the DSP chain
    // stereo wrapper - internally uses processMulti
    state->chain.process(state->inL.data(), state->inR.data(), state->outL.data(), state->outR.data(), static_cast<unsigned int>(framesPerBuffer));

    // Interleave planar output back to PortAudio output buffer
    for (unsigned long i = 0; i < framesPerBuffer; ++i) {
        out[2 * i + 0] = state->outL[i];
        out[2 * i + 1] = state->outR[i];
    }

    return paContinue;
}

// Main
int main(int argc, char* argv[]) 
{
    // disable stdio sync and force line buffering for pipe mode
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);
    setvbuf(stdin, nullptr, _IOLBF, 0);

    std::cerr << "AudioMIX DSP is running!" << std::endl;

    // Parse CLI flags
    bool headlessMode = false;
    // original audio init calls
    for (int i = 1; i < argc; ++i) {
        if (std::string(argv[i]) == "--headless") headlessMode = true;
    }

    // start control-plane listener on a dedicated thread
    ControlBus control;
    std::thread controlThread(controlLoop, &control);
    controlThread.detach();

    // Set up AudioState
    AudioState state;
    state.sampleRate = 44100.0;
    state.maxBlockSize = 512;
    state.control = &control;

    state.inL.resize(state.maxBlockSize, 0.0f);
    state.inR.resize(state.maxBlockSize, 0.0f);
    state.outL.resize(state.maxBlockSize, 0.0f);
    state.outR.resize(state.maxBlockSize, 0.0f);

    state.chain.setSampleRate(state.sampleRate);
    state.chain.setMaxBlockSize(state.maxBlockSize);

    /*
      Build DSP chain
      Signal flow:
      Choir -> Shimmer -> EQ -> Compressor -> Gain -> Clipper
    */
    auto* choir = state.chain.emplaceModule<DigitalChoirModule>(8);
    choir->setParameter("wet", 0.8f);
    choir->setParameter("spread", 1.0f);

    // Shimmer - can process "chorused" audio
    auto* shimmer = state.chain.emplaceModule<ShimmerModule>();
    // overall mix
    shimmer->setParameter("wet", 0.4f);
    // tail length
    shimmer->setParameter("feedback", 0.7f);
    // full shimmer strength
    shimmer->setParameter("octave_mix", 1.0f);
    // tail pre-delay
    shimmer->setParameter("delay_ms", 550.0f);

    // EQ module
    auto* eq = state.chain.emplaceModule<audiomix::dsp::EqModule>();
    state.eq = eq;
    control.eq = eq;

    // Reverb module - FDN
    auto* reverb = state.chain.emplaceModule<AscensionReverbModule>();
    reverb->setParams(ReverbParams{
        // 20 ms onset separation
        .pre_delay_ms = 20.0f,
        // T60: 2.5 sec tail
        .decay_s = 2.5f,
        // slightly large room
        .size = 1.2f,
        // warm, moderate HF absorption
        .damping = 0.55f,
        // subtle, sits under the mix
        .wet = 0.25f,
        // full stereo
        .width = 1.0f,
        .sample_rate = static_cast<int>(state.sampleRate)
    });
    state.reverb = reverb;

    // Compressor module
    // catches the reverb tail
    auto* compressor = state.chain.emplaceModule<CompressorModule>();
    // defaults
    compressor->setParams(CompressorParams{});
    state.compressor = compressor;
    control.compressor = compressor;

    // Gain module
    auto* gain = state.chain.emplaceModule<audiomix::dsp::GainModule>();
    gain->setGainDb(0.0f);
    state.gain = gain;

    // Clipper module
    auto* clipper = state.chain.emplaceModule<ClipperModule>();
    clipper->setDriveDb(0.0f);
    clipper->setCeilingDb(-0.1f);
    clipper->setMix(1.0f);
    clipper->setMode(ClipperModule::Mode::Soft);
    state.clipper = clipper;

    // Headless mode (hardware agnostic)
    // adds sinks BEFORE prepare() so sinks get prepare/reset correctly
    if (headlessMode) state.chain.emplaceModule<NullSink>();

    state.chain.prepare();

    // PortAudio setup
    // skipped in headless mode
    PaStream* stream = nullptr;
    if (!headlessMode) {
        // initialize PortAudio via main_utils.cpp
        if (!initializeAudio()) return 1;

        // PortAudio Stream setup
        PaDeviceIndex inDev = Pa_GetDefaultInputDevice();
        PaDeviceIndex outDev = Pa_GetDefaultOutputDevice();

        if (outDev == paNoDevice) {
            std::cerr << "No default output device found.\n";
            std::cerr << "Available devices:\n";
            list_audio_devices();
            shutdownAudio();
            return 1;
        }

        const PaDeviceInfo* outInfo = Pa_GetDeviceInfo(outDev);
        if (!outInfo) {
            std::cerr << "Output device info is null.\n";
            list_audio_devices();
            shutdownAudio();
            return 1;
        }

        // output is req
        PaStreamParameters outputParams{};
        outputParams.device = outDev;
        outputParams.channelCount = 2;
        outputParams.sampleFormat = paFloat32;
        outputParams.suggestedLatency = outInfo->defaultLowOutputLatency;

        // input is optional: if missing, pass nullptr and callback will receive
        PaStreamParameters inputParamsStorage{};
        PaStreamParameters* inputParamsPtr = nullptr;
        if (inDev != paNoDevice) {
            const PaDeviceInfo* inInfo = Pa_GetDeviceInfo(inDev);
            if (inInfo) {
                inputParamsStorage.device = inDev;
                inputParamsStorage.channelCount = 2;
                inputParamsStorage.sampleFormat = paFloat32;
                inputParamsStorage.suggestedLatency = inInfo->defaultLowInputLatency;
                inputParamsPtr = &inputParamsStorage;
            } else {
                std::cerr << "Warn: input device info is null; continuing output-only.\n";
            }
        } else {
            std::cerr << "Warn: no default input device; continuing output-only.\n";
        }

        PaError err = Pa_OpenStream(&stream, inputParamsPtr, &outputParams, state.sampleRate, state.maxBlockSize, paNoFlag, audioCallback, &state);

        if (err != paNoError) {
            std::cerr << "Err: Pa_OpenStream failed: " << Pa_GetErrorText(err) << "\n";
            list_audio_devices();
            shutdownAudio();
            return 1;
        }

        err = Pa_StartStream(stream);
        if (err != paNoError) {
            std::cerr << "Err: Pa_StartStream failed: " << Pa_GetErrorText(err) << "\n";
            Pa_CloseStream(stream);
            shutdownAudio();
            return 1;
        }

        std::cout << "Audio stream running. Press Ctrl+C to exit.\n";
    }

    // Run loop
    if (!headlessMode) {
        while (Pa_IsStreamActive(stream) == 1) Pa_Sleep(100);
        Pa_StopStream(stream);
        Pa_CloseStream(stream);
        shutdownAudio();
    } else {
        // Headless run loop (no PortAudio)
        while (true) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}
