# AudioMIX
# audioscript/compiler/audio2script/dev_sanity.py

from audioscript.compiler.audio2script.script_ir import ShowIR, Section, Event

def main():
    show = ShowIR(audio_path="audio/samples/cvltiv8r_clean.wav", bpm=128.0)

    intro = Section(start=0.0, end=8.0, label="intro")
    drop = Section(start=8.0, end=32.0, label="drop")

    show.add_section(intro)
    show.add_section(drop)

    show.add_event(Event(time=0.0, type="ambient_fade_in", params={"intensity": 0.3}))
    show.add_event(Event(time=8.0, type="drop_flash", params={"strobe_intensity": 1.0}))

    print ("ShowIR:", show)
    print ("Sorted events:")
    for e in show.sorted_events():
        sec = show.find_section_for_time(e.time)
        print (f" t={e.time:.3f}s, type={e.type}, section={sec.label if sec else 'None'}")

if __name__ == "__main__":
    main()
