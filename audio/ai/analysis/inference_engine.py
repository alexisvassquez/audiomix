# audiomix
# AudioMIX
# audio/ai/analysis/inference_engine.py

"""
AudioMIX Inference Engine

This module takes extracted audio features and
infers high-level events, moods, and lighting profiles.
It generates an AudioScript with inferred commands
and a lighting profile based on detected emotions,
BPM, and audience engagement.
"""

import os
import json
from audio.ai.planners.lighting_orchestrator import apply_dynamic_zoning
from audio.led.color_profiles import get_color_for_mood, get_pattern_for_mood
from audio.led.audio_reactive import react_to_audio
from audio.ai.modules.tempo_analysis import get_bpm_from_audio
from audio.ai.analysis.audience_listener import detect_hype

# Mood-to-Zone Mapping Matrix
# This mapping defines which zones to activate based on the inferred mood and BPM range.
ZONE_MAP = {
    "calm": {
        "zones": ["ceiling"],
        "bpm_range": (0, 100)
    },
    "melancholy": {
        "zones": ["back_wall"],
        "bpm_range": (0, 110)
    },
    "excited": {
        "zones": ["front_strip"],
        "bpm_range": (120, 140)
    },
    "intense": {
        "zones": ["front_strip", "ceiling"],
        "bpm_range": (140, 160)
    },
    "euphoric": {
        "zones": ["front_strip", "ceiling", "back_wall"],
        "bpm_range": (160, 200)
    }
}

def interpret_from_features(features, output_path="audio/analysis_output/inferred_script.audioscript"):
    """
    Takes extracted audio features and infers high-level events and moods.
    Generates an AudioScript with inferred commands
      and a lighting profile based on detected emotions.
    """
    events = []
    times = features.get("times", [])
    rms = features.get("rms", [])
    spectral_centroid = features.get("spectral_centroid", [])

    if not times or not rms:
        print ("[!] Missing required features: 'times' and 'rms'")
        return

    # Lite "drop" detection: low-high RMS jump
    for i in range(1, len(rms) -1):
        prev_rms = rms[i - 1]
        current_rms = rms[i]
        next_rms = rms[i + 1]

        if prev_rms > current_rms < next_rms and (next_rms - current_rms) > 0.1:
            timestamp = float(times[i])
            events.append(f"@{timestamp: .2f}s drop()")

    # High spectral centroid = 'bright' tag
    for i, sc in enumerate(spectral_centroid):
        if sc > 3000: # Hz threshold for brightness
            timestamp = float(times[i])
            events.append(f"@{timestamp:.2f}s brightness()")

    # Save AudioScript
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        for line in sorted(set(events)):
            f.write(line + "\n")

    print (f"Inference complete. {len(events)} AudioScript commands written to inferred_script.audioscript.")

    # Emotion Inference
    emotion_tags = set()
    if emotion_tags:
        generate_lighting_profile(emotion_tags)
        apply_dynamic_zoning(emotion_tags, bpm=128) # Infer BPM

    avg_rms = sum(rms) / len(rms)
    avg_centroid = sum(spectral_centroid) / len(spectral_centroid) if spectral_centroid else 0

    """
    Simple heuristic-based emotion inference:
    - Low RMS + low centroid = "calm", "warm"
    - High RMS + high centroid = "intense", "bright"
    - Cross-analysis can yield "excited" or "melancholy"
    """
    if avg_rms < 0.05:
        emotion_tags.add("calm")
    elif avg_rms > 0.2:
        emotion_tags.add("intense")

    if avg_centroid < 1500:
        emotion_tags.add("warm")
    elif avg_centroid > 3500:
        emotion_tags.add("bright")

    # Cross-analysis
    if "intense" in emotion_tags and "bright" in emotion_tags:
        emotion_tags.add("excited")
    elif "calm" in emotion_tags and "warm" in emotion_tags:
        emotion_tags.add("melancholy")

    # Output to AudioScript header block
    if emotion_tags:
        events.insert(0, f"# emotion: {', '.join(sorted(emotion_tags))}")

    # Dyamic zone-based lighting activation based on BPM and audience hype
    bpm = get_bpm_from_audio(features)
    zone = ["main"]

    if detect_hype(threshold_db=70):
        """
        Hype detection: If the audience is hyped (e.g., loud cheering), we can override the mood to "excited" and activate all zones for maximum impact.
        This is a real-time reactive feature that adds an extra layer of interactivity based on audience engagement."""
        print ("[🔥] Hype detected - overring mood to 'excited' in 'stage_front'")
        emotion_tags.add("excited")
        zone = ["front_strip", "ceiling", "back_wall"]

    if emotion_tags:
        events.insert(0, f"# emotion: {', '.join(sorted(emotion_tags))}")
        generate_lighting_profile(emotion_tags, bpm=bpm, zone=zone)

# Mood-to-Zone Resolver
def get_zones_for_mood_bpm(mood, bpm):
    """
    This function takes a mood and BPM value and returns the appropriate zones to activate based on the ZONE_MAP configuration.
    If the mood is not found or the BPM is out of range, it returns a default zone.
    """
    default = ["main"]
    config = ZONE_MAP.get(mood)
    if not config:
        return default
    low, high = config["bpm_range"]
    if low <= bpm <= high:
        return config["zones"]
    return default

# LED Mapping
def generate_lighting_profile(emotion_tags, bpm=128, zone=["main"], output_path="audio/analysis_output/lighting_profile.json"):
    """
    Generates a lighting profile JSON based on the inferred emotion tags, BPM, and zones. This profile can be used by the lighting orchestrator to create dynamic light shows that match the music's mood and energy.
    """
    profile = []

    for mood in emotion_tags:
        color = get_color_for_mood(mood)
        pattern = get_pattern_for_mood(mood)
        for zone in zones:
            profile.append({
                "mood": mood,
                "color": {"r": color[0], "g": color[1], "b": color[2]},
                "pattern": pattern,
                "zones": zones
            })
            # Dispatch real-time command
            zones = get_zones_for_mood_bpm(mood, bpm)
            for z in zones:
                react_to_audio(mood, bpm, z)

    with open(output_path, "w") as f:
        json.dump(profile, f, indent=2)

    print(f"✅ Lighting profile written to {output_path}")
