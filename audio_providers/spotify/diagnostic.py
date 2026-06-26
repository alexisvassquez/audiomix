# audiomix
# AudioMIX
# spotify/diagnostic.py

import os
import requests
import certifi
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

# Force requests to use certifi CA bundle globally
requests.Session.verify = certifi.where()

# Load environment variables from .env
load_dotenv()

# Get credentials from environment
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

# Initialize Spotipy with client credentials
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIPY_CLIENT_ID,
    client_secret=SPOTIPY_CLIENT_SECRET
))

# Test a single public track
track_id = "4PTG3Z6ehGkBFwjybzWkR8"

try:
    features = sp.audio_features([track_id])
    print ("[✅] Success! Here is a sample of the audio features:")
    print (features[0])
except Exception as e:
    print ("[💥] Goblin calling audio_features():")
    print(e)
