// AudioMIX
// audio/dsp/core/sample_player.cpp
//
// dr_wav.h is vendored from github.com/mackron/dr_libs repository.

#define DR_WAV_IMPLEMENTATION
#include "dr_wav.h"
#include "sample_player.h"

#include <cmath>

namespace audiomix::dsp {
    bool SamplePlayer::play(const std::string& path, float gain, bool loop, double engineSr) {
        drwav wav;
        if (!drwav_init_file(&wav, path.c_str(), nullptr)) return false;

        const uint64_t nframes = wav.totalPCMFrameCount;
        const unsigned ch = wav.channels;
        const unsigned sr = wav.sampleRate;

        std::vector<float> inter(static_cast<size_t>(nframes) * (ch ? ch : 1));
        const uint64_t read = drwav_read_pcm_frames_f32(&wav, nframes, inter.data());
        drwav_uninit(&wav);
        if (read == 0 || ch == 0) return false;

        auto data = std::make_shared<SampleData>();

        // de-interleave to planar L/R at the file's native rate
        std::vector<float> nativeL(read), nativeR(read);
        for (uint64_t i = 0; i < read; ++i) {
            const float l = inter[i * ch + 0];
            const float r = (ch > 1) ? inter[i * ch + 1] : l;
            nativeL[i] = l;
            nativeR[i] = r;
        } 

        // Resampling.
        // Resample to the engine rate
        // linear interp, done once off the audio thread
        if (sr > 0 && engineSr > 0.0 && static_cast<double>(sr) != engineSr) {
            const double ratio = engineSr / static_cast<double>(sr);
            const uint64_t outFrames = static_cast<uint64_t>(std::llround(static_cast<double>(read) * ratio));
            data->L.resize(outFrames);
            data->R.resize(outFrames);
            for (uint64_t i = 0; i < outFrames; ++i) {
                const double srcPos = static_cast<double>(i) / ratio;
                const uint64_t i0 = static_cast<uint64_t>(srcPos);
                const uint64_t i1 = (i0 + 1 < read) ? (i0 + 1) : (read - 1);
                const float frac = static_cast<float>(srcPos - static_cast<double>(i0));
                data->L[i] = nativeL[i0] + (nativeL[i1] - nativeL[i0]) * frac;
                data->R[i] = nativeR[i0] + (nativeR[i1] - nativeR[i0]) * frac;
            }
            data->frames = outFrames;
            data->sampleRate = static_cast<int>(engineSr);
        } else {
            data->L = std::move(nativeL);
            data->R = std::move(nativeR);
            data->frames = read;
            data->sampleRate = static_cast<int>(sr);
        }

        Voice v;
        v.data = std::move(data);
        v.gain = gain;
        v.loop = loop;
        v.pos = 0;
        {
            std::lock_guard<std::mutex> lk(mMutex);
            mPending.push_back(std::move(v));
        }
        return true;
    }
} // namespace audiomix::dsp