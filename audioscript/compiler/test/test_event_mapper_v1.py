# audiomix
# AudioMIX
# audioscript/compiler/test/test_event_mapper_v1.py

from audioscript.compiler.audio2script.analyzer import analyze_audio
from audioscript.compiler.audio2script.event_mapper import map_features_to_events
from audioscript.compiler.audio2script.script_generator import generate_audioscript

# Test harness for Event Mapper v1

def main():
    audio_path = "audio/samples/full/cvltiv8r_clean.wav"

    print ("Analyzing audio...")
    frames, sections, bpm = analyze_audio(audio_path)

    print (f"\nBPM: {bpm}")
    print (f"Sections detected: {len(sections)}")
    for s in sections:
        print (f" - {s.label}: {s.start:.3f} -> {s.end:.3f}")

    print ("\nMapping events...")
    show = map_features_to_events(audio_path, frames, sections, bpm)
    events = show.sorted_events()

    print (f"Total events generated: {len(events)}")
    for e in events[:15]:    # print first 15 events to avoid walls of text
        print (f" t={e.time:.3f} {e.type} {e.params}")

    print ("\nGenerating AudioScript...")
    script = generate_audioscript(show)

    print ("\n=== GENERATED AUDIOSCRIPT ===\n")
    print (script)

if __name__ == "__main__":
    main()
