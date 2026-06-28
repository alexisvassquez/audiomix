// audiomix
// AudioMIX
// audio/dsp/modules/subbass_isolation.h
//
/*
  ***Biquad Filter***
  We use a Direct Form I implementation for clarity
  We are using biquad because:
    a. it's efficient (very cheap per sample - talking about tech debt)
    b. stable for low freqs
    c. perfect for band-limiting sub-bass region
*/

#pragma once
#include <cmath>
#include <cstdint>

#include "../core/subbass_bus.h"

namespace audiomix::dsp {

class Biquad {
public:
    // coefficients are stored in "a0-normalized" form
    // that means a0 is assumed to be 1.0 after normalization
    void setCoeffs(float b0, float b1, float b2, float a1, float a2) {
        this->b0=b0; this->b1=b1; this->b2=b2;
        this->a1=a1; this->a2=a2;
    }

    // process one sample
    // this is called per-sample inside the audio thread
    inline float process(float x) {
        // Direct Form I structure
        float y = b0*x + z1;
        z1 = b1*x - a1*y + z2;
        z2 = b2*x - a2*y;

        return y;
    }

    void reset() {
        z1 = 0.0f;
        z2 = 0.0f;
    }

private:
    float b0=1, b1=0, b2=0;
    float a1=0, a2=0;

    // delay elements
    float z1=0, z2=0;
};

/*
  *** RBJ Cookbook Filter Generator***
  These functions compute stable lowpass and highpass
  coeffs using the well-known RBJ filter formulas.

  RBJ is:
    a. industry standard
    b. numerically stable
    c. and simple to implement <3
*/

struct RBJ {
    static void lowpass(float fs, float f0, float Q, Biquad& bq);
    static void highpass(float fs, float f0, float Q, Biquad& bq);
};

/*
  SubBassIsolationModule
  Purpose:
    - to isolate sub-bass freqs (default is 20-90 Hz)
    - compute RMS energy in that band
    - smooth the meter
    - publish results to SubBassBus

  This modules does not modify the audio signal.
  It merely passes audio through *untouched*
  It also acts as an analysis + control stage.
  The module keeps our DSP graph modular and predictable.
*/

class SubBassIsolationModule {
public:
    explicit SubBassIsolationModule(SubBassBus* bus = nullptr)
        : bus_(bus) {}

    // called when sample rate changes
    // filters must be recalculated
    void setSampleRate(double sr) {
        sampleRate_ = sr;
        recalcFilters();
    }

    void prepare(unsigned int /*maxBlock*/) {
        reset();
        recalcFilters();
    }

    // Master + Booth (L/R)
    // lowpass/highpass
    void reset() {
        l_hp_.reset();
        l_lp_.reset();
        r_hp_.reset();
        r_lp_.reset();
        env_ = 0.0f;
    }

    // define sub-band region
    // low clamp prevents nonsense values
    void setBand(float lowHz, float highHz) {
        lowHz_ = clamp(lowHz, 10.0f, 200.0f);
        highHz_ = clamp(highHz, lowHz_ + 1.0f, 250.0f);

        recalcFilters();

        if (bus_) {
            bus_->bandLowHz.store(lowHz_, std::memory_order_relaxed);
            bus_->bandHighHz.store(highHz_, std::memory_order_relaxed);
        }
    }

    void setEnabled(bool e) { enabled_ = e; }

    /*
      meter smoothing time in milliseconds (ms)
      we're smoothing because raw RMS fluctuates wildly
      EQ decisions must be stable
    */
    void setMeterSmoothingMs(float ms) {
        meterMs_ = clamp(ms, 1.0f, 500.0f);
    }

    /*
      Core Processing:
      audio passes through untouched
      sub band is isolated internally
      RMS is computed per block
      smoothed mono energy is stored in bus
    */
    void process(const float* inL, const float* inR,
                 float* outL, float* outR,
                 unsigned int n)
    {
        // pass-through
        for (unsigned int i=0; i<n; ++i) {
            outL[i] = inL[i];
            outR[i] = inR[i];
        }

        if (!enabled_ || !bus_) return;

        double sumL = 0.0;
        double sumR = 0.0;

        for (unsigned int i=0; i<n; ++i) {
            // apply HPF then LPf to isolate band
            float sl = l_lp_.process(l_hp_.process(inL[i]));
            float sr = r_lp_.process(r_hp_.process(inR[i]));

            sumL += static_cast<double>(sl) * static_cast<double>(sl);
            sumR += static_cast<double>(sr) * static_cast<double>(sr);
        }

        float rmsL = (n > 0) ? std::sqrt(sumL / n) : 0.0f;
        float rmsR = (n > 0) ? std::sqrt(sumR / n) : 0.0f;
        float rmsMono = 0.5f * (rmsL + rmsR);

        // smooth the meter
        float a = meterAlpha();
        env_ = a * env_ + (1.0f - a) * rmsMono;

        bus_->rmsL.store(rmsL, std::memory_order_relaxed);
        bus_->rmsR.store(rmsR, std::memory_order_relaxed);
        bus_->rmsMono.store(env_, std::memory_order_relaxed);
    }

private:
    static float clamp(float v, float lo, float hi) {
        return (v < lo) ? lo : (v > hi) ? hi : v;
    }

    // converts smoothing time (ms) into exponential decay coeff
    float meterAlpha() const {
        const float tau = meterMs_ * 0.001f;    // convert ms -> seconds
        const float fs = (float)sampleRate_;

        if (tau <= 0.0f || fs <= 1.0f) return 0.0f;

        return std::exp(-1.0f / (tau * fs));
    }

    void recalcFilters() {
        if (sampleRate_ <= 1.0) return;

        // Q = 0.707 gives Butterworth-like response
        // standard Butterworth response types allow for flexible
        // well-behaved digital filter implementation
        RBJ::highpass((float)sampleRate_, lowHz_, 0.707f, l_hp_);
        RBJ::lowpass((float)sampleRate_, highHz_, 0.707f, l_lp_);

        RBJ::highpass((float)sampleRate_, lowHz_, 0.707f, r_hp_);
        RBJ::lowpass((float)sampleRate_, highHz_, 0.707f, r_lp_);
    }

private:
    SubBassBus * bus_ = nullptr;

    double sampleRate_ = 44100.0;    // 44.1 kHz
    bool enabled_ = true;

    float lowHz_ = 20.0f;            // lowest Hz band
    float highHz_ = 90.0f;            // highest Hz band
    float meterMs_ = 60.0f;

    float env_ = 0.0f;

    Biquad l_hp_, l_lp_;
    Biquad r_hp_, r_lp_;
};

}  // namespace audiomix::dsp
