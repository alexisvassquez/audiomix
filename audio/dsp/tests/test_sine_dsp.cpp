// audiomix
// AudioMIX
// audio/dsp/tests/test_sine_dsp.cpp
//
/*
  Gratification test: generates a 440 Hz sine wave and runs it through the full AudioMIX DSP chain.
  (DigitalChoir -> Shimmer -> EQ -> Gain -> Clipper)
  We can now hear what the engine actually sounds like for the first time.

  Run with ./build/test_sine_dsp from root
*/

#include <iostream>
#include <vector>
#include <cmath>
#include <atomic>
#include <chrono>
#include <thread>
#include <portaudio.h>

#include "../core/dsp_chain.h"
#include "../modules/digital_choir.h"
#include "../modules/shimmer.h"
#include "../modules/eq_module.h"
#include "../modules/gain_module.h"
#include "../modules/clipper_module.h"

using namespace audiomix::dsp;

// 44.1 kHz
static constexpr double SAMPLE_RATE = 44100.0;
// 512 block size
static constexpr unsigned int BLOCK = 512;
// A4 - change to taste
static constexpr double FREQ_HZ = 440.0;
// safe listening level
static constexpr float AMPLITUDE = 0.4f;
// how long to play in seconds
static constexpr int DURATION_SEC = 8;

struct SineState {
    DspChain chain;
    double phase = 0.0;
    double phaseStep = (2.0 * M_PI * FREQ_HZ) / SAMPLE_RATE;

    std::vector<float> inL, inR;
    std::vector<float> outL, outR;
};

static int audioCallback(const void*, void* outputBuffer, unsigned long framesPerBuffer, const PaStreamCallbackTimeInfo*, PaStreamCallbackFlags, void* userData) {
    auto* state = static_cast<SineState*>(userData);
    float* out = static_cast<float*>(outputBuffer);

    // generate a sine wave into both input channels
    for (unsigned long i = 0; i < framesPerBuffer; ++i) {
        float sample = AMPLITUDE * static_cast<float>(std::sin(state->phase));
        state->inL[i] = sample;
        state->inR[i] = sample;
        state->phase += state->phaseStep;
        if (state->phase >= 2.0 * M_PI)
            state->phase -= 2.0 * M_PI;
    }

    // run through the full DSP chain
    state->chain.process(state->inL.data(), state->inR.data(),
                         state->outL.data(), state->outR.data(),
                        static_cast<unsigned int>(framesPerBuffer));
    
    // interleave stereo output
    for (unsigned long i = 0; i < framesPerBuffer; ++i) {
        out[2 * i + 0] = state->outL[i];
        out[2 * i + 1] = state->outR[i];
    }

    return paContinue;
}

int main() {
    std::cout << "AudioMIX sine wave test - 440Hz through full DSP chain\n";
    std::cout << "Chain: DigitalChoir -> Shimmer -> EQ -> Gain -> Clipper\n\n";

    // Build DSP chain (mirrors main.cpp exactly)
    SineState state;
    state.inL.resize(BLOCK, 0.0f);
    state.inR.resize(BLOCK, 0.0f);
    state.outL.resize(BLOCK, 0.0f);
    state.outR.resize(BLOCK, 0.0f);

    state.chain.setSampleRate(SAMPLE_RATE);
    state.chain.setMaxBlockSize(BLOCK);

    // DigitalChoir
    auto* choir = state.chain.emplaceModule<DigitalChoirModule>(8);
    choir->setParameter("wet", 0.8f);
    choir->setParameter("spread", 1.0f);

    // Shimmer
    auto* shimmer = state.chain.emplaceModule<ShimmerModule>();
    shimmer->setParameter("wet", 0.4f);
    shimmer->setParameter("feedback", 0.7f);
    shimmer->setParameter("octave_mix", 1.0f);
    shimmer->setParameter("delay_ms", 550.0f);

    // EQ
    // flat - no coloring, just confirming it passes signal
    state.chain.emplaceModule<EqModule>();

    // Gain
    auto* gain = state.chain.emplaceModule<GainModule>();
    gain->setGainDb(0.0f);

    // Clipper
    // soft clipping
    auto* clipper = state.chain.emplaceModule<ClipperModule>();
    clipper->setDriveDb(0.0f);
    clipper->setCeilingDb(-0.1f);
    clipper->setMix(1.0f);
    clipper->setMode(ClipperModule::Mode::Soft);

    state.chain.prepare();

    // PortAudio setup
    if (Pa_Initialize() != paNoError) {
        std::cerr << "PortAudio init failed\n";
        return 1;
    }

    PaStreamParameters outParams{};
    outParams.device = Pa_GetDefaultOutputDevice();
    outParams.channelCount = 2;
    outParams.sampleFormat= paFloat32;
    outParams.suggestedLatency = Pa_GetDeviceInfo(outParams.device)->defaultLowOutputLatency;

    if (outParams.device == paNoDevice) {
        std::cerr << "No output device found\n";
        Pa_Terminate();
        return 1;
    }

    // Find the PulseAudio device explicitly
    PaDeviceIndex targetDevice = Pa_GetDefaultOutputDevice();
    int deviceCount = Pa_GetDeviceCount();
    for (int i = 0; i < deviceCount; ++i) {
        const PaDeviceInfo* info = Pa_GetDeviceInfo(i);
        if (info && std::string(info->name).find("pulse") != std::string::npos) {
            targetDevice = i;
            std::cout << "Using PulseAudio device: " << info->name << "\n";
            break;
        }
    }
    outParams.device = targetDevice;

    // nullptr = no input (silence)
    PaStream* stream = nullptr;
    PaError err = Pa_OpenStream(&stream, nullptr, &outParams, SAMPLE_RATE, BLOCK, paNoFlag, audioCallback, &state);

    if (err != paNoError) {
        std::cerr << "Pa_OpenStream failed: " << Pa_GetErrorText(err) << "\n";
        Pa_Terminate();
        return 1;
    }

    Pa_StartStream(stream);
    std::cout << "Playing for " << DURATION_SEC << " seconds... (Ctrl+C to stop early)\n\n";

    // Play for DURATION_SEC then stop cleanly
    std::this_thread::sleep_for(std::chrono::seconds(DURATION_SEC));

    Pa_StopStream(stream);
    Pa_CloseStream(stream);
    Pa_Terminate();

    std::cout << "Done. How did she sound? 🎛️\n";
    return 0;
}