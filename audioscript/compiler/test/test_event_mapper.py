# audiomix
# AudioMIX
# audioscript/compiler/test/test_event_mapper.py

from audioscript.compiler.audio2script.analyzer import analyze_audio
from audioscript.compiler.audio2script.event_mapper import map_features_to_events

# Test Event Mapper v0
def main():
    frames, sections, bpm = analyze_audio("dummy.wav")
    show = map_features_to_events("dummy.wav", sections, bpm)

    print ("Generated Events:")
    for e in show.sorted_events():
        print (f"{e.time:.2f}s -> {e.type} ({e.params})")

if __name__ == "__main__":
    main()
