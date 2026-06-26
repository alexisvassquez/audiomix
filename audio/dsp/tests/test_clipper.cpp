// audiomix
// AudioMIX
// audio/dsp/tests/test_clipper.cpp
//
// A test for the Clipper module

#include <cmath>
#include <iomanip>
#include <iostream>
#include <vector>
#include <fstream>
#include <string>
#include <algorithm>

#include "audio/dsp/modules/clipper_module.h"

using audiomix::dsp::ClipperModule;

static void print_buffer(const char* label, const std::vector<float>& buf) {
    std::cout << label << ": ";
    for (float x : buf) {
        std::cout << std::fixed << std::setprecision(4) << x << " ";
    }
    std::cout << "\n";
}

static void write_csv(const std::vector<float>& input,
               const std::vector<float>& output,
               const std::string& filename)
{
    std::ofstream file(filename);
    file << "index,input,output\n";

    for (size_t i = 0; i < input.size(); ++i) {
        file << i << "," << input[i] << "," << output[i] << "\n";
    }
}

int main() {
    ClipperModule clipper;

    constexpr double sampleRate = 48000.0;
    constexpr unsigned int frames = 2048;

    clipper.prepare(sampleRate, frames);

    // force instant params for testing
    clipper.setMode(ClipperModule::Mode::Hard);
    clipper.setDriveDb(12.0f);
    clipper.setCeilingDb(-6.0f);
    clipper.setMixTarget(1.0f, 0.0f);

    std::vector<float> inL(frames);
    std::vector<float> inR(frames);
    std::vector<float> outL(frames, 0.0f);
    std::vector<float> outR(frames, 0.0f);

    // Ramp input: intentionally exceeds ceiling after drive
    for (unsigned int i = 0; i < frames; ++i) {
        float x = -1.2f + (2.4f * static_cast<float>(i) / static_cast<float>(frames - 1));
        inL[i] = x;
        inR[i] = x;
    }

    print_buffer("Input", inL);

    // warm-up smoothing
    clipper.process(inL.data(), inR.data(), outL.data(), outR.data(), frames);

    // clear outputs before the real pass
    std::fill(outL.begin(), outL.end(), 0.0f);
    std::fill(outR.begin(), outR.end(), 0.0f);

    // run actual test
    clipper.process(inL.data(), inR.data(), outL.data(), outR.data(), frames);

    print_buffer("Output L", outL);
    print_buffer("Output R", outR);

    float maxAbs = 0.0f;
    for (float x : outL) {
        maxAbs = std::max(maxAbs, std::fabs(x));
    }

    std::cout << "Max abs output: " << std::fixed << std::setprecision(4) << maxAbs << "\n";

    // write csv
    write_csv(inL, outL, "waveform.csv");

    return 0;
}

