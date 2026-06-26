# audiomix
# AudioMIX
# audioscript/compiler/test/test_smooth_sections.py

from audioscript.compiler.audio2script.analyzer import analyze_audio
from audioscript.compiler.audio2script.smooth_sections import smooth_sections

# Test stub for section smoother

def main():
    frames, sections, bpm = analyze_audio("audio/samples/full/cvltiv8r_clean.wav")  # sample audio file

    print ("\nRAW SECTIONS:", len(sections))
    for s in sections[:10]:
        print (f" - {s.label} {s.start:.3f} -> {s.end:.3f}")

    merged = smooth_sections(sections)

    print ("\nMERGED SECTIONS:", len(merged))
    for s in merged:
        print (f" - {s.label} {s.start:.3f} -> {s.end:.3f}")

if __name__ == "__main__":
    main()
