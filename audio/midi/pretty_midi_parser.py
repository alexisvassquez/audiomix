# audiomix
# AudioMIX
# audio/midi/pretty_midi_parser.py

import pretty_midi
import sys

def parse_midi_pretty(file_path):
    midi_data = pretty_midi.PrettyMIDI(file_path)

    print (f"File: {file_path}")
    print (f"Tempo (estimated): {midi_data.estimate_tempo():.2f} BPM")
    print (f"Duration: {midi_data.get_end_time():.2f} seconds\n")

    for i, instrument in enumerate(midi_data.instruments):
        name = instrument.name if instrument.name else f"Instrument {i}"
        print (f"🎹 {name} ({'Drums' if instrument.is_drum else 'Melodic'})")
        for note in instrument.notes:
            print (f"  Note: {pretty_midi.note_number_to_name(note.pitch)} | "
                   f"Start: {note.start:.2f}s | End: {note.end:.2f}s | "
                   f"Velocity: {note.velocity}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print ("Usage: python3 audio/midi/pretty_midi_pasrser.py <path_to_midi_file>")
    else:
        parse_midi_pretty(sys.argv[1])
