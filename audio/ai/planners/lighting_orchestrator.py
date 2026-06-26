# audiomix
# AudioMIX
# audio/ai/planners/lighting_orchestrator.py

# Orchestrates dynamic lighting effects based on predicted emotion tags and BPM.
# This module takes predicted emotion tags and BPM as input,
#  and applies corresponding lighting effects to different zones of the room.
# It uses a predefined mapping of emotions to lighting zones, and includes
#  fallback logic to assign zones based on BPM if emotion tags are missing.
# Example usage:
#   python3 -m audio.ai.planners.lighting_orchestrator

import json
from audio.led.audio_reactive import react_to_audio
from audio.led.controller import LightController
from audio.ai.modules.tempo_analysis import get_bpm_from_audio

# Emotion-to-zone mapping
EMOTION_ZONE_MAP = {
    "excited": "front_strip",
    "calm": "ceiling",
    "melancholy": "back_wall",
    "intense": "floor",
    "reflective": "side_panels",
    "happy": "centerpiece",
    "angry": "strobe_beam",
    "chill": "ambient_sides",
    "confident": "main_wall"
}

# Fallback logic: assign by BPM
def get_zone_by_bpm(bpm):
    if bpm > 140:
        return "front_strip"
    elif bpm > 120:
        return "main_wall"
    elif bpm > 100:
        return "ambient_sides"
    else:
        return "top_ceiling"


def apply_dynamic_zoning(emotion_tags, bpm=120, debug=False):
    """
    Applies dynamic lighting zoning based on emotion tags and BPM.
    Args:      
        emotion_tags: List of predicted emotion tags for the current track.
        bpm: Tempo of the track, used for fallback zoning if no emotions are tagged.
        debug: If True, prints detailed debug information about zoning decisions.
    """
    controller = LightController()

    for mood in emotion_tags:
        zone = EMOTION_ZONE_MAP.get(mood, get_zone_by_bpm(bpm))
        if debug:
            print (f"[Juniper2.0] Applying mood '{mood}' to zone '{zone}' at {bpm} BPM")
        react_to_audio(mood, bpm, zone)

def load_features(path="audio/analysis_output/features_summary.json"):
    """
    Loads precomputed audio features from a JSON file.
    """
    with open(path, "r") as f:
        return json.load(f)

def run_lighting_orchestration():
    """
    Main function to run the lighting orchestration
      based on predicted emotion tags and BPM.
    """
    data = load_features()
    bpm = int(data.get("tempo", [120])[0])
    emotion_tags = []

    # TEMP: Manually define emotion for test
    if bpm > 140:
        emotion_tags.append("intense")
    elif bpm > 120:
        emotion_tags.append("excited")
    else:
        emotion_tags.append("calm")

    apply_dynamic_zoning(emotion_tags, bpm)

if __name__ == "__main__":
    run_lighting_orchestration()
