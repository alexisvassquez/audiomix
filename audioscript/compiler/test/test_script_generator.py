# audiomix
# AudioMIX
# audioscript/compiler/test/test_script_generator.py

from audioscript.compiler.audio2script.analyzer import analyze_audio
from audioscript.compiler.audio2script.event_mapper import map_features_to_events
from audioscript.compiler.audio2script.script_generator import generate_audioscript

"""
Small test that uses analyzer stub, event mapper, and script generator to
generate AudioScript (AS) code blocks
"""

def main():
    audio_path = "audio/samples/cvltiv8r_clean.wav"
    frames, sections, bpm = analyze_audio(audio_path)
    show = map_features_to_events(audio_path, sections, bpm)
    script = generate_audioscript(show)

    print ("=== Generated AudioScript ===")
    print (script)

if __name__ == "__main__":
    main()
