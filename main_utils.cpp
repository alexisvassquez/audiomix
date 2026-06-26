// audiomix
// AudioMIX
// main_utils.cpp

// Replaces old audio_utils.cpp

#include "main.h"

#include <iostream>
#include <cstdlib>

#include <portaudio.h>

// ALSA log suppression (Linux)
// Set AUDIOMIX_ALSA_DEBUG=1 to restore ALSA logs without recompiling
#if defined(__linux__)
    #include <alsa/asoundlib.h>
    static void audiomix_alsa_error_handler(const char* /*file*/,
                                          int /*line*/,
                                          const char* /*function*/,
                                          int /*err*/,
                                          const char* /*fmt*/,
                                          ...) {
        // quiet ALSA diagnostic output
        return;
    }
#endif

// Initialize PortAudio
bool initializeAudio() {
    // install ALSA error suppression unless explicitly disabled
    // only affects ALSA's own stderr spam, not PortAudio errors
#if defined(__linux__)
    const char* alsaDebug = std::getenv("AUDIOMIX_ALSA_DEBUG");
    if (!(alsaDebug && std::string(alsaDebug) == "1")) {
        snd_lib_error_set_handler(audiomix_alsa_error_handler);
    }
#endif

    PaError err = Pa_Initialize();
    if (err != paNoError) {
        std::cerr << "PortAudio initialization failed: "
                 << Pa_GetErrorText(err) << std::endl;
        return false;
    }

    std::cout << "PortAudio initialized successfully!" << std::endl;
    return true;
}

// Shut down PortAudio
void shutdownAudio() {
    Pa_Terminate();
    std::cout << "PortAudio shutdown completed." << std::endl;
}

// List audio devices
extern "C" void list_audio_devices() {
    int numDevices = Pa_GetDeviceCount();
    if (numDevices < 0) {
        std::cerr << "Pa_GetDeviceCount error:\n";
        return;
    }

    for (int i = 0; i < numDevices; ++i) {
        const PaDeviceInfo* info = Pa_GetDeviceInfo(i);
        if (!info) {
            std::cerr << "Device " << i << ": <null>\n";
            continue;
        }

        std::cout << "Device " << i << ": " << info->name << "\n";
    }
}
