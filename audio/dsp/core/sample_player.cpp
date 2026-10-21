// AudioMIX
// audio/dsp/core/sample_player.cpp
//
// dr_wav.h is vendored from github.com/mackron/dr_libs repository.

#define DR_WAV_IMPLEMENTATION
#include "dr_wav.h"
#include "sample_player.h"

namespace audiomix::dsp {
    bool SamplePlayer::play(const std::string& path, float gain, bool loop, double /*engineSr*/) {
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
        data->sampleRate = static_cast<int>(sr);
        data->frames = read;
        data->L.resize(read);
        data->R.resize(read);
        for (uint64_t i = 0; i < read; ++i) {
            const float l = inter[i * ch + 0];
            const float r = (ch > 1) ? inter[i * ch + 1] : l;
            data->L[i] = l;
            data->R[i] = r;
        } 
        // note: assumes the wav's rate == engine rate (44100), as defined in
        // main.cpp
        // For now, it feeds it 44.1k files or plays off-speed.
        // TODO: Resampling.

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