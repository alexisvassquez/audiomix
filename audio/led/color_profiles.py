# AudioMIX
# audio/led/color_profiles.py
#
# Color and mood-based mapping to LED patterns
# Used for live performance engine

MOOD_COLOR_MAP = {
    "melancholy": (30, 60, 90), # Cool blue
    "hype": (255, 20, 20), # Intense red
    "chill": (0, 255, 180), # Aqua
    "reflective": (200, 160, 255), # Lilac
    "confident": (255, 215, 0),    # Gold
    "angry": (213, 0, 0), # Deep red
    "peaceful": (0, 255, 127), # Spring green
    "happy": (255, 223, 0), # Yellow
    "calm": (171, 71, 188), # Purple
    "energetic": (255, 109, 0), # Orange
    "sad": (41, 98, 255), # Blue
    "relaxed": (0, 255, 128) # Green
}

# Named colors for direct glow()/pulse() calls - distinct from
# MOOD_COLOR_MAP above.
COLOR_NAME_MAP = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "magenta": (255, 0, 255),
    "yellow": (255, 255, 0),
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "pink": (255, 105, 180),
    "lilac": (200, 160, 255),
    "gold": (255, 215, 0),
    "aqua": (0, 255, 180),
}

MOOD_PATTERN_MAP = {
    "happy": "blink",
    "calm": "wave",
    "energetic": "chase",
    "sad": "fade",
    "relaxed": "sparkle",
    "angry": "strobe",
    "melancholy": "fade",
    "hype": "strobe",
    "chill": "wave",
    "reflective": "glow",
    "confident": "blink",
    "peaceful": "breathe"
}

def get_color_for_mood(mood):
    return MOOD_COLOR_MAP.get(mood.lower(), (255, 255, 255)) # Default to white

def get_pattern_for_mood(mood):
    return MOOD_PATTERN_MAP.get(mood.lower(), "steady")

def _hex_to_rgb(hex_str):
    """
    Parse '#RRGGBB' (or 'RRGGBB') into an (r, g, b) tuple.
    Returns None if it isn't a valid 6-digit hex string, so
    callers can fall back to the named-color lookup instead.
    """
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6:
        return None
    try:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None

def get_color_for_name(color_name):
    """
    Resolve a color name ('cyan') or hex code ('#00FFFF') to RGB.
    This is the lookup glow()/pulse() should use.
    Default to COLOR_NAME_MAP, not MOOD_COLOR_MAP.
    """
    if color_name.startswith("#"):
        rgb = _hex_to_rgb(color_name)
        if rgb:
            return rgb
        # Default to white
        return COLOR_NAME_MAP.get(color_name.lower(), (255, 255, 255))
