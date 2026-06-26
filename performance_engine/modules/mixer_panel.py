# AudioMIX
# performance_engine/modules/mixer_panel.py

from performance_engine.modules.session_builder import AudioSession

def print_menu():
    print ("\n🎛️  Mixer Panel Options")
    print ("1. List Tracks")
    print ("2. Add Track")
    print ("3. Adjust Volume")
    print ("4. Adjust Pan")
    print ("5. Mute/Unmute Track")
    print ("6. Solo/Unsolo Track")
    print ("7. Delete Track")
    print ("8. Save Session")
    print ("9. Load Session")
    print ("0. Exit")

def get_float(prompt):
    # prompt user for a float value with error checking
    try:
        return float(input(prompt))
    except ValueError:
        print ("❌ Invalid input. Please enter a number")
        return get_float(prompt)

def mixer_cli():
    # create a new session
    session = AudioSession()

    # extend Track class dynamically to support mute/solo flag
    for track in session.tracks:
        setattr(track, "mute", False)
        setattr(track, "solo", False)

    while True:
        print_menu()
        choice = input("Select an option: ")

        if choice == "1":
            # show track list with mute/solo info
            print ("\n🎼  Tracks:")
            for i, track in enumerate(session.tracks):
                mute = getattr(track, "mute", False)
                solo = getattr(track, "solo", False)
                flags = []
                if mute: flags.append("MUTED")
                if solo: flags.append("SOLO")
                tag = " | ".join(flags) if flags else ""
                print (f"{i+1}. {track.name} ({track.type}) @ {track.start}s vol={track.volume} pan={track.pan} {tag}")

        elif choice == "2":
            # add new track w/ user input
            path = input("File path: ")
            name = input("Track name: ")    # custom track name
            start = get_float("Start time (s): ")
            vol = get_float("Volume (dB): ")
            pan = get_float("Pan (-1.0 left to 1.0 right, 0 = center): ")

            session.add_track(path, start=start, volume=vol, pan=pan)
            session.tracks[-1].name = name or Path(path).stem
            # apply mute/solo attributes to newly added track
            setattr(session.tracks[-1], "mute", False)
            setattr(session.tracks[-1], "solo", False)
            print (f"✅ Track '{session.tracks[-1].name}' added.")

        elif choice == "3":
            # adjust track volume
            index = int(input("Track number to adjust volume: ")) - 1
            if 0 <= index < len(session.tracks):
                vol = get_float("New volume (dB): ")
                session.tracks[index].volume = vol
                print ("🔊 Volume updated.")
            else:
                print ("❌ Invalid track number.")

        elif choice == "4":
            # adjust panning
            index = int(input("Track number to adjust pan: ")) - 1
            if 0 <= index < len(session.tracks):
                pan = get_float("New pan (-1.0 to 1.0, 0 = center): ")    # left to right stereo
                session.tracks[index].pan = pan
                print ("🔈 Pan updated.")
            else:
                print ("❌ Invalid track number.")

        elif choice == "5":
            # toggle mute
            index = int(input("Track number to mute/unmute: ")) - 1
            if 0 <= index < len(session.tracks):
                track = session.tracks[index]
                current = getattr(track, "mute", False)
                setattr(track, "mute", not current)
                print ("🔇 Muted." if not current else "🔊 Unmuted.")
            else:
                print ("❌ Invalid track number.")

        elif choice == "6":
            # toggle solo
            # mutes all other tracks
            index = int(input("Track number to solo/unsolo: ")) - 1
            if 0 <= index < len(session.tracks):
                track = session.tracks[index]
                current = getattr(track, "solo", False)
                setattr(track, "solo", not current)
                print ("🎚️ Solo enabled." if not current else "🎚️ Solo disabled.")
            else:
                print ("❌ Invalid track number.")

        elif choice == "7":
            # deletes a track
            index = int(input("Track number to delete: ")) - 1
            if 0 <= index < len(session.tracks):
                deleted = session.tracks.pop(index)
                print (f"❌ Deleted {deleted.file_path.name}")
            else:
                print ("❌ Invalid track number.")

        elif choice == "8":
            # saves session to json
            path = input("Save path: ")    # e.g., my_mix.json (as an example)
            session.save(path)
            print (f"📥 Session saved to {path}")

        elif choice == "9":
            # load session from json and add dynamic attributes
            path = input("Load path: ")    # e.g., my_mix.json (example)
            try:
                session.load(path)
                for track in session.tracks:
                    setattr(track, "mute", False)
                    setattr(track, "solo", False)
                print (f"📤 Session loaded from {path}")
            except Exception as e:
                print (f"❌ Failed to load session: {e}")

        elif choice == "0":
            print ("Exiting mixer...")
            break

        else:
            print ("❌ Invalid choice. Try again.")

# Main function for testing on CLI
if __name__ == "__main__":
    mixer_cli()
