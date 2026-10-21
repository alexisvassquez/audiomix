// AudioMIX
// audio/dsp/core/sample_player.h
//
// Polyphonic sample mixer. Decodes WAVs on the control thread; mixes
// active voices into a stereo buffer on the audio thread.
// Lives in main.cpp's callback and sums clips into the DSP chain's input.

#pragma once
#include <vector>
#include <memory>
#include <mutex>
#include <string>
#include <atomic>
#include <cstdint>
#include <algorithm>

namespace audiomix::dsp {
    // decoded, immutable sample data
    // planar, mono is duplicated to both.
    struct SampleData {
        std::vector<float> L;
        std::vector<float> R;
        int sampleRate = 44100;    // 44.1 khz
        uint64_t frames = 0;
    };

    struct Voice {
        std::shared_ptr<const SampleData> data;
        uint64_t pos = 0;
        float gain = 1.0f;
        bool loop = false;
        bool finished = false;
    };

    class SamplePlayer {
        public:
            // Control thread: decode 'path' and queue it for playback
            // Returns false if the file can't be opened/read.
            bool play(const std::string& path, float gain, bool loop, double engineSr);

            // Control thread: stop everything on the next audio block.
            void stopAll() {
                std::lock_guard<std::mutex> lk(mMutex);
                mPending.clear();
                mStopAll.store(true, std::memory_order_release);
            }

            // Audio thread: add active voices on top of whatever is in L/R
            void mixInto(float* L, float* R, unsigned int nframes) {
                // pull in newly-queued voices w/o blocking the audio thread
                if (mMutex.try_lock()) {
                    for (auto& v : mPending) mActive.push_back(std::move(v));
                    mPending.clear();
                    mMutex.unlock();
                }
                if (mStopAll.exchange(false, std::memory_order_acq_rel)) mActive.clear();

                for (auto& v : mActive) {
                    const SampleData* d = v.data.get();
                    if (!d) { v.finished = true; continue; }
                    for (unsigned int i = 0; i < nframes; ++i) {
                        if (v.pos >= d->frames) {
                            if (v.loop) v.pos = 0;
                            else { v.finished = true; break; }
                        }
                        L[i] += d->L[v.pos] * v.gain;
                        R[i] += d->R[v.pos] * v.gain;
                        ++v.pos;
                    }
                }
                mActive.erase(std::remove_if(mActive.begin(), mActive.end(), [](const Voice& v) { return v.finished; }), mActive.end());
            }
        
        private:
            // audio thread only
            std::vector<Voice> mActive;
            // control -> audio (under mMutex)
            std::vector<Voice> mPending;
            std::mutex mMutex;
            std::atomic<bool> mStopAll{ false };
    };
} // namespace audiomix::dsp