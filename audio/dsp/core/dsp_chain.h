// audiomix
// AudioMIX
// audio/dsp/core/dsp_chain.h
//
/*
   Simple plugin chain that owns modules and runs them in order
   Defaults to 4 channels
   Adds zero buffer for missing inputs
   Safe passthrough behavior for null output channels
   Lazily prepares buffers if needed
*/

#pragma once
#include <memory>
#include <vector>
#include <algorithm>

#include "../core/dsp_module.h"
#include "../core/process_spec.h"
#include "../core/process_context.h"

namespace audiomix::dsp {

class DspChain {
public:
    void setSampleRate(double sr) { mSampleRate = sr; }
    void setMaxBlockSize(unsigned int size) { mMaxBlockSize = size; }

    // default to 4 (Master L/R + Booth L/R)
    void setNumChannels(unsigned int ch) { mNumChannels = (ch == 0 ? 1u : ch); }
    unsigned int getNumChannels() const { return mNumChannels; }

    template <typename ModuleT, typename... Args>
    ModuleT* emplaceModule(Args&&... args) {
        auto mod = std::make_unique<ModuleT>(std::forward<Args>(args)...);
        ModuleT* raw = mod.get();
        mModules.emplace_back(std::move(mod));
        return raw;
    }

    // ProcessSpec
    // setup-time config (prepare phase)
    void prepare(const ProcessSpec& spec) {
        mSampleRate = spec.sampleRate;
        mMaxBlockSize = spec.maxBlockSize;
        mNumChannels = (spec.numChannels == 0 ? 1u : spec.numChannels);
        prepare();
    }

    void prepare() {
        if (mSampleRate <= 0.0 || mMaxBlockSize == 0 || mNumChannels == 0) return;

        // zero buffer used when an input channel pointer is null
        mZero.assign(mMaxBlockSize, 0.0f);

        // allocate ping-pong buffers: channels (A and B), each
        mTmpA.assign(mNumChannels, std::vector<float>(mMaxBlockSize, 0.0f));
        mTmpB.assign(mNumChannels, std::vector<float>(mMaxBlockSize, 0.0f));

        // scratch pointer arrays (avoid allocating each process call)
        mInPtrs.resize(mNumChannels, nullptr);
        mOutPtrs.resize(mNumChannels, nullptr);

        for (auto& m : mModules) {
            m->prepare(mSampleRate, mMaxBlockSize);
            m->reset();
        }

        mPrepared = true;
    }

    // ProcessContext
    // runtime block data (process phase)
    // small wrapper enough to est architecture
    void process(ProcessContext& ctx) {
        processMulti(ctx.inputs, ctx.outputs, ctx.numChannels, ctx.numFrames);
    }

    // Multichannel process entry pt
    void processMulti(const float* const* inputs,
                      float* const* outputs,
                      unsigned int numChannels,
                      unsigned int numFrames)
    {
        if (numChannels == 0 || numFrames == 0) return;

        // respects a call from a diff channel count than configured
        // but clamp to configured buffers for safety
        const unsigned int chCount = std::min(numChannels, mNumChannels);

        // lazy-prepare (if needed)
        if (!mPrepared || mTmpA.empty() || mTmpA[0].size() != mMaxBlockSize) {
            prepare();
        }
        if (!mPrepared) return;

        if (numFrames > mMaxBlockSize) {
            // hard clamp to prevent OOB writes
            numFrames = mMaxBlockSize;
        }

        // fast passthrough if no modules
        if (mModules.empty()) {
            for (unsigned int ch = 0; ch < chCount; ++ch) {
                const float* in = inputs && inputs[ch] ? inputs[ch] : mZero.data();
                float* out = outputs ? outputs[ch] : nullptr;
                if (out) std::copy(in, in + numFrames, out);
            }
            return;
        }

        // helper to build pointer arrays for module calls
        auto buildPtrs = [&](const float* const* srcIn, float* const* srcOut) {
            for (unsigned int ch = 0; ch < chCount; ++ch) {
                mInPtrs[ch] = (srcIn && srcIn[ch]) ? srcIn[ch] : mZero.data();
                mOutPtrs[ch] = (srcOut) ? srcOut[ch] : nullptr;
            }
        };

        // First module: read from real input -> tmpA
        for (unsigned int ch = 0; ch < chCount; ++ch) {
            mOutPtrs[ch] = mTmpA[ch].data();
        }
        buildPtrs(inputs, mOutPtrs.data());
        mModules.front()->processMulti(mInPtrs.data(), mOutPtrs.data(), chCount, numFrames);

        bool usingA = true;

        // Remaining modules ping-pong between tmp buffers
        for (std::size_t i = 1; i < mModules.size(); ++i) {
            // set inputs from prev tmp, outputs to other tmp
            for (unsigned int ch = 0; ch < chCount; ++ch) {
                const float* prev = usingA ? mTmpA[ch].data() : mTmpB[ch].data();
                float* next = usingA ? mTmpB[ch].data() : mTmpA[ch].data();
                mInPtrs[ch] = prev;
                mOutPtrs[ch] = next;
            }
            usingA = !usingA;

            mModules[i]->processMulti(mInPtrs.data(), mOutPtrs.data(), chCount, numFrames);
        }

        // Final tmp -> outputs (null safe)
        for (unsigned int ch = 0; ch < chCount; ++ch) {
            const float* finalBuf = usingA ? mTmpA[ch].data() : mTmpB[ch].data();
            float* out = outputs ? outputs[ch] : nullptr;
            if (out) std::copy(finalBuf, finalBuf + numFrames, out);
        }
    }

    // convenience stereo wrapper
    // keeps older call sites happy
    void process(const float* inL, const float* inR,
                 float* outL, float* outR,
                 unsigned int numFrames)
    {
        const float* ins[2] = { inL, inR };
        float* outs[2] = { outL, outR };
        processMulti(ins, outs, 2, numFrames);
    }

private:
    double mSampleRate = 44100.0;
    unsigned int mMaxBlockSize = 512;
    unsigned int mNumChannels = 4;

    bool mPrepared = false;

    std::vector<std::unique_ptr<DspModule>> mModules;

    // ping-pong buffers
    std::vector<std::vector<float>> mTmpA;
    std::vector<std::vector<float>> mTmpB;

    // null-input safety
    std::vector<float> mZero;

    // scratch pointer arrays (no per-call allocations)
    std::vector<const float*> mInPtrs;
    std::vector<float*> mOutPtrs;
};

} // namespace audiomix::dsp
