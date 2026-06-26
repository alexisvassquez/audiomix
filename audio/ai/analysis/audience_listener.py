# AudioMIX
# audio/ai/analysis/audience_listener.py

# This script listens to the microphone input 
# for a specified duration and calculates 
# the average loudness in decibels (dB). 
# If the average loudness exceeds a defined threshold,
# it indicates that the audience is hyped or cheering.

import numpy as np

def detect_hype(threshold_db=65, listen_time=3, chunk=1024, rate=44100):
    """
    Listens to the mic input and returns True if average loudness
    exceeds the threshold (indicating hype or cheering)
    """
    # lazy, only loads when called
    # helps with boot time for AS shell
    import pyaudio
    from torchaudio.functional import loudness
    p = pyaudio.PyAudio()

    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    frames_per_buffer=chunk)

    print (f"[Juniper2.0] Listening for audience reaction...")

    loudness_readings = []

    for _ in range(int(rate / chunk * listen_time)):
        data = stream.read(chunk, exception_on_overflow=False)
        audio_data = np.frombuffer(data, dtype=np.int16)
        rms = np.sqrt(np.mean(np.square(audio_data)))
        db = 20 * np.log10(rms) if rms > 0 else -np.inf
        loudness_readings.append(db)

    stream.stop_stream()
    stream.close()
    p.terminate()

    avg_db = np.mean([d for d in loudness_readings if not np.isnan(d)])
    print (f"[Juniper2.0] Average Loudness: {avg_db:.2f} dB")

    return avg_db >= threshold_db
