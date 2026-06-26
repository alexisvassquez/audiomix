# audiomix
# AudioMIX
# audioscript/compiler/audio2script/run.py

import argparse
from audioscript.compiler.audio2script.analyzer import analyze_audio
from audioscript.compiler.audio2script.smooth_sections import smooth_sections
from audioscript.compiler.audio2script.event_mapper import map_features_to_events
from audioscript.compiler.audio2script.script_generator import generate_audioscript

"""
Universal Runner Script
Creates a single command that can be ran for any sound file.
"""

def main():
    parser = argparse.ArgumentParser(description="AudioMIX AudioScript Compiler")
    parser.add_argument("--file", required=True, help="Path to audio file")
    parser.add_argument("--save", action="store_true", help="Save output .as file")
    args = parser.parse_args()

    audio_path = args.file

    print ("\nAnalyzing audio...")
    frames, raw_sections, bpm = analyze_audio(audio_path)

    print (f" - BPM: {bpm:.2f}")
    print (f" - Raw sections: {len(raw_sections)}")

    print ("\nSmoothing sections...")
    sections = smooth_sections(raw_sections)
    print (f" - Merged sections: {len(sections)}")

    print ("\nMapping events...")
    show = map_features_to_events(audio_path, frames, sections, bpm)
    events = show.sorted_events()
    print (f" - Total events: {len(events)}")

    print ("\nGenerating AudioScript...")
    script = generate_audioscript(show)

    print ("\n=== AudioScript Code ===\n")
    print (script)

    if args.save:
        out_file = audio_path.rsplit(".", 1)[0] + ".as"
        with open(out_file, "w") as f:
            f.write(script)
        print (f"\n📥  Saved script to: {out_file}")

if __name__ == "__main__":
    main()
