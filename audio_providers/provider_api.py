# AudioMIX
# audio_providers/provider_api.py

from typing import Protocol, Dict, Any, Optional

class Provider(Protocol):
    name: str
    def connect(self, **kwargs) -> None: ...
    def current_user(self) -> Dict[str, Any]: ...
    def find_track(self, query: str) -> Optional[Dict[str, Any]]: ...
    def start_playback(self, uri: str, **opts) -> None: ...
    def stop(self) -> None: ...

_registry: Dict[str, Provider] = {}

def register_provider(p: Provider) -> None:
    _registry[p.name] = p

def get_provider(name: str) -> Provider:
    if name not in _registry:
        raise KeyError(f"Provider '{name}' not registered")
    return _registry[name]
