# AudioMIX
# spotify/extract_spotify_features.py

import time
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json
import csv
import os
from pathlib import Path
from dotenv import load_dotenv

# Load credentials if using a .env
load_dotenv()

# Spotify Developer credentials
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
SPOTIPY_REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

# Playlist URI (extracted from the link)
HEAPR_PLAYLIST_URI = "spotify:playlist:2vRjkgpmYzFt4JMntYsN5C"

# Output paths
output_dir = Path("spotify/data")
output_dir.mkdir(parents=True, exist_ok=True)
json_path = output_dir / "heapr_features.json"
csv_path = output_dir / "heapr_features.csv"

# Initialize Spotify API
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET,
))

# Get all track IDs from the playlist
def get_track_ids(playlist_uri):
    results = sp.playlist_tracks(playlist_uri)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return [track['track']['id'] for track in tracks if track['track'].get('id')]

# Get audio features for all tracks
def get_audio_features(track_ids, chunk_size=25):
    audio_features = []
    for i in range(0, len(track_ids), chunk_size):
        chunk = track_ids[i:i+chunk_size]
        try:
            features = sp.audio_features(chunk)
            print (f"[📦] Processed chunk {i}-{i+len(chunk)} ({len(audio_features)} total so far)")

            if features:    # safety check
                for feature in features:
                    if feature is None:
                        continue
                    audio_features.append({
                        "id": feature["id"],
                        "tempo": feature["tempo"],
                        "energy": feature["energy"],
                        "danceability": feature["danceability"],
                        "valence": feature["valence"],
                        "loudness": feature["loudness"],
                        "speechiness": feature["speechiness"],
                        "acousticness": feature["acousticness"],
                        "instrumentalness": feature["instrumentalness"],
                        "liveness": feature["liveness"],
                        "duration_ms": feature["duration_ms"],
                        "key": feature["key"],
                        "mode": feature["mode"],
                        "time_signature": feature["time_signature"]
                     })
        except spotipy.exceptions.SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 5))
                print (f"[🕜] Rate limit hit. Retrying after {retry_after}s...")
                time.sleep(retry_after + 1)
            elif e.http_status == 403:
                print (f"[🛑] 403 Forbidden on chunk {i}-{i+len(chunk)}. Skipping those track IDs:")
                print (chunk)
            continue
        except Exception as e:
            print (f"[💥] Unexpected error on chunk {i}+{i+len(chunk)}: {e}")
            continue
        time.sleep(0.5)
    return audio_features

# Write to JSON
def save_as_json(data, path):
    if not data:
        print (f"[!] No valid features to write to {path}.")
        return
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print (f"[✅] Saved {len(data)} entries to {path}")

# Write to CSV
def save_as_csv(data, path):
    if not data:
        print (f"[!] No valid features found to save to {path}.")
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print (f"[✅] Saved {len(data)} entries to {path}")

# Run extraction
if __name__ == "__main__":
    print ("🎧 Extracting tracks from HEAPR...")
    track_ids = get_track_ids(HEAPR_PLAYLIST_URI)
    print (f"[🎶] Found {len(track_ids)} tracks")

    print ("🧠 Fetching audio features...")
    features = get_audio_features(track_ids)

    save_as_json(features, json_path)
    save_as_csv(features, csv_path) 
    print ("✨ Done! Your sonic baby has been preserved.")
