# AudioMIX
# audio/midi/midi_tag_classifier.py

import os
import json

def suggest_tag(tempo, density, avg_velocity, instruments):
    has_drums = any(inst["is_drum"] for inst in instruments)
    melodic_instruments = [inst for inst in instruments if not inst["is_drum"]]
    total_melodic_notes = sum(inst["num_notes"] for inst in melodic_instruments)
    num_instruments = len(instruments)

    # --- Classical Check ---
    if not has_drums and num_instruments == 1 and density > 6:
        return "classical_virtuoso"
    if not has_drums and density > 2 and avg_velocity < 70:
        return "classical_expressive"

    # --- Experimental / Retro ---
    if has_drums and any("unknown" in inst["name"] for inst in instruments):
        return "experimental_genre"
    if "square_wave" in str(instruments).lower() or "synth" in str(instruments).lower():
        return "retro_style"

    # --- Electronic / EDM ---
    if has_drums and tempo >= 120 and density > 3:
        return "electronic_dance"
    if has_drums and tempo >= 140:
        return "fast_edm"

    # --- Ambient / Minimalism ---
    if tempo < 90 and density < 1.5 and avg_velocity < 60:
        return "ambient_minimalism"

    # --- Pop Genre ---
    if has_drums and tempo > 100 and avg_velocity > 80:
        return "modern_pop"

    # --- Default fallback ---
    return "instrumental_undefined"

def classify_feature_file(path):
    with open(path, "r") as f:
        data = json.load(f)

    tempo = data.get("tempo_bpm", 0)
    density = data.get("note_density_per_sec", 0)
    avg_vel = data.get("avg_velocity", 0)
    instruments = data.get("instruments", [])

    tag = suggest_tag(tempo, density, avg_vel, instruments)
    data["tag_suggestion"] = tag

    with open(path, "w") as f:
        json.dump(data, f, indent=2)

    print (f"[✅] {os.path.basename(path)} -> {tag}")
    return { "file": os.path.basename(path), "tag": tag }

def classify_directory(folder_path):
    results = []
    for file in os.listdir(folder_path):
        if file.endswith("_features.json"):
            full_path = os.path.join(folder_path, file)
            result = classify_feature_file(full_path)
            results.append(result)

    # Write master tag index
    index_path = os.path.join(folder_path, "midi_tag_index.json")
    with open(index_path, "w") as f:
        json.dump(results, f, indent=2)

    print (f"\n🗃️  All files classified. Index saved to: {index_path}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print ("Usage: python3 midi_tag_classifier.py <feature_json_folder>")
    else:
        classify_directory(sys.argv[1])
