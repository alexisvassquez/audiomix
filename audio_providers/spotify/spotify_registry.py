# AudioMIX
# audio_provieders/spotify/spotify_registry.py

from .audio_providers.provider_api import register_provider
from .audio_providers.spotify.spotify_adapter import SpotifyAdapter

spotify = SpotifyAdapter(
    client_id="<env>", client_secret="<env>",
    redirect_uri="http://localhost:8888/callback",
    scopes="user-read-playback-state user-modify-playback-state playlist-read-private streaming"
)
register_provider(spotify)
