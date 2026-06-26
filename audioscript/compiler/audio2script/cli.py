# audiomix
# AudioMIX
# audioscript/compiler/audio2script/cli.py

import sys
import os

from audioscript.compiler.audio2script.analyzer import analyze_audio
from audioscript.compiler.audio2script.event_mapper import map_features_to_events
from audioscript.compiler.audio2script.script_generator import generate_audioscript

# CLI runner that saves result to a `.as` file
def main():
    if len(sys.argv) < 2:
        print ("Usage: python3 -m audio.ai.compiler.audio2script.cli <audio_path>")
        raise SystemExit(1)

    audio_path = sys.argv[1]

    frames, sections, bpm = analyze_audio(audio_path)
    show = map_features_to_events(audio_path, sections, bpm)
    script = generate_audioscript(show)

    out_path = os.path.splitext(audio_path)[0] + ".as"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(script)

    print (f"Generated AudioScript: {out_path}")

if __name__ == "__main__":
    main()
