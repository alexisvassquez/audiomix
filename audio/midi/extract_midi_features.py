# AudioMIX
# audio/midi/extract_midi_features.py

import pretty_midi
import json
import os
import sys

def extract_features(file_path):
    midi_data = pretty_midi.PrettyMIDI(file_path)

    # Extract basic metadata
    tempo = midi_data.estimate_tempo()
    duration = midi_data.get_end_time()
    num_tracks = len(midi_data.instruments)

    note_list = []
    velocity_list = []

    instruments = []

    for inst in midi_data.instruments:
        inst_name = inst.name if inst.name else "unknown"
        instruments.append({
            "name": inst_name,
            "is_drum": inst.is_drum,
            "num_notes": len(inst.notes)
        })

        for note in inst.notes:
            note_list.append(note.pitch)
            velocity_list.append(note.velocity)

    # Extract top-level features
    note_count = len(note_list)
    avg_velocity = sum(velocity_list) / len(velocity_list) if velocity_list else 0
    note_density = note_count / duration if duration else 0

    # Convert first 10 notes to pitch names
    note_names = [pretty_midi.note_number_to_name(p) for p in note_list[:10]]

    features = {
        "file_name": os.path.basename(file_path),
        "duration_seconds": round(duration, 3),
        "tempo_bpm": round(tempo, 2),
        "note_count": note_count,
        "note_density_per_sec": round(note_density, 3),
        "avg_velocity": round(avg_velocity, 2),
        "first_10_notes": note_names,
        "instruments": instruments,
        "tag_suggestion": None
    }

    return features

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: python3 extract_midi_features.py <path_to_midi>")
        sys.exit(1)

    midi_file = sys.argv[1]
    features = extract_features(midi_file)

    # Save to JSON next to file
    output_path = os.path.splitext(midi_file)[0] + "_features.json"
    with open(output_path, 'w') as f:
        json.dump(features, f, indent=2)

    print (f"[✅] Features extracted and saved to: {output_path}")
