# AudioMIX
# performance_engine/modules/provider_commands.py

from audio_providers.provider_api import get_provider
from performance_engine.utils.shell_output import say

def play_provider(title_or_uri, provider="spotify"):
    p = get_provider(provider)
    uri = title_or_uri
    if not title_or_uri.startswith("spotify:") and provider == "spotify":
        track = p.find_track(title_or_uri)
        if not track:
            say(f"[ERROR] Track not found: {title_or_uri}", "⚠️")
            return
        uri = track["uri"]
    p.start_playback(uri)
    say(f"[PROVIDER] Playing via {provider}: {title_or_uri}", "🎵")

def stop_provider(provider="spotify"):
    p = get_provider(provider)
    p.stop()
    say(f"[PROVIDER] Stopped {provider}", "⏹️")

def register():
    return {
        "provider.play": play_provider,    # e.g, play("<song_title>, "spotify")
        "provider.stop": stop_provider
    }
