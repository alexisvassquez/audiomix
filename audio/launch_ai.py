import subprocess

file_path = "/home/wholesomedegenerate/audiomix/audio/samples/ilariio_soft-chill-vibes.mp3"
print ("Spotibot Analyzing: {file_path}")

result = subprocess.run(
    ["python3", "ai/analyze_audio.py", file_path],
    capture_output=True,
    text=True
)

print ("=== Audio Features ===")
print (result.stdout)
