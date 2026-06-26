# AudioMIX
# audio_providers/spotify/spotify_adapter.py

import spotipy
from spotipy.oauth2 import SpotifyOAth
from typing import Dict, Any, Optional

class SpotifyAdapter:
    name = "spotify"

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, scopes: str):
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id, client_secret=client_secret,
            redirect_ui=redirect_uri, scope=scopes
        ))

    def connect(self, **kwargs) -> None:
        _ = self.current_user()

    def current_user(self) -> Dict[str, Any]:
        return self.sp.current_user()

    def find_track(self, query: str) -> Optional[Dict[str, Any]]:
        res = self.sp.search(q=query, type="track", limit=1)
        items = res.get("tracks", {}).get("items", [])
        return items[0] if items else None

    def start_playback(self, uri: str, **opts) -> None:
        self.sp.start_playback(uris=[uri], **opts)

    def stop(self) -> None:
        self.sp.pause_playback()
