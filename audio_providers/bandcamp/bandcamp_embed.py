# AudioMIX
# audio_provider/bandcamp/bandcamp_embed.py

@dataclass
class BandcampEmbed:
    name: str = "bandcamp-embed"

    def get_embed_html(self, page_url: str, width: int = 400, height: int = 120) -> str:
        # to be sandboxed in Electron UI later
        return f'<iframe src="{page_url}" width="{width}" height="{height}" frameborder="0"></iframe>'

    def open_external(self, page_url: str) -> None:
        webbrowser.open(page_url)
