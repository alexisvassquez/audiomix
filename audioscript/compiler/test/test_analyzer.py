# audiomix
# AudioMIX
# audioscript/compiler/test/test_analyzer.py

from audioscript.compiler.audio2script.analyzer import analyze_audio

# Test script to verify analyzer's stub logic
def main():
    frames, sections, bpm = analyze_audio("dummy.wav")
    print ("BPM:", bpm)
    print ("Sections:", sections[:2])
    print ("First 3 frames:", frames[:3])

if __name__ == "__main__":
    main()
