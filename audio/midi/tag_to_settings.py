# AudioMIX
# audio/midi/tag_to_settings.py

import json
import os
import sys
from audio.eq.eq_commands import eq_preset

def load_tag_map(tag_map_path):
    with open(tag_map_path, 'r') as f:
        return json.load(f)

def load_feature_json(feature_path):
    with open(feature_path, 'r') as f:
       return json.load(f)

def get_settings_for_tag(tag, tag_map):
    return tag_map.get(tag, {
        "eq_preset": "default",
        "lighting_scene": "none",
        "mood": "neutral"
    })

def apply_settings(settings):
    print ("🧠  Applying system settings:")
    print (f"  🎛️  EQ Prest:        {settings['eq_preset']}")
    print (f"  💡 Lighting Scene:  {settings['lighting_scene']}")
    print (f"  🎭 Mood Setting:    {settings['mood']}")

    eq_preset(settings["eq_preset"])    # Calls preset by name
    trigger_lighting_scene(settings["lighting_scene"])

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print ("Usage: python3 tag_to_settings.py <feature_json> <tag_map.json>")
        sys.exit(1)

    feature_path = sys.argv[1]
    tag_map_path = sys.argv[2]

    feature_data = load_feature_json(feature_path)
    tag_map = load_tag_map(tag_map_path)

    tag = feature_data.get("tag_suggestion", "unknown")
    settings = get_settings_for_tag(tag, tag_map)
    apply_settings(settings) 
