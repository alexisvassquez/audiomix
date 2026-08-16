import json

from audio.led.controller import LightController

if __name__ == "__main__":
    controller = LightController()

    with open("audio/analysis_output/lighting_profile.json", "r") as f:
        lighting_profile = json.load(f)

    print ("✅ Loaded lighting profile. Applying moods...\n")

    for entry in lighting_profile:
        mood = entry["mood"]
        color = (entry["color"]["r"], entry["color"]["g"], entry["color"]["b"])
        pattern = entry["pattern"]
        zone = entry.get("zone", "main")

        print(f"[+] Zone: {zone} >> Mood: {mood} >> Pattern: {pattern}, Color: {color}")
        controller.apply_mood(mood, color, pattern, zone)
