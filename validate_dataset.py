#!/usr/bin/env python3

# AudioMIX
# Validates AudioMIX_metadata.csv and labels.jsonl consistency

import os
import csv
import json
import sys
from pathlib import Path

try:
    import soundfile as sf
except ImportError:
    sf = None

# Config
# --------------
DATASET_DIR = Path("audio/ai/datasets")
CLIPS_DIR = DATASET_DIR / "clips"
META_PATH = DATASET_DIR / "AudioMIX_metadata.csv"
LABELS_PATH = DATASET_DIR / "labels.jsonl"

REQUIRED_COLS = [
    "file", "bpm", "key", "genre", "source", "split",
    "energy", "valence", "danceability", "reference_only"
]
ALLOWED_SPLITS = {"train", "val", "test", "reference"}

# Helpers
# -------------
def info(msg): print (f"🟢  {msg}")
def warn(msg): print (f"⚠️  {msg}")
def error(msg): print (f"❌  {msg}")

# Validation functions
# -------------

# Check metadata structure and column sanity
def validate_metadata():
    if not META_PATH.exists():
        error(f"Missing file: {META_PATH}")
        return False

    with open(META_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            warn("AudioMIX_metadata.csv has no headers or is empty.")
            return True    # not an error yet

        missing = [c for c in REQUIRED_COLS if c not in reader.fieldnames]
        if missing:
            error(f"Missing columns in AudioMIX_metadata.csv: {missing}")
            return False

        for i, row in enumerate(reader, 1):
            if not row.get("file"):
                warn(f"[Row {i}] missing 'file' value.")
            split = row.get("split", "").lower()
            if split and split not in ALLOWED_SPLITS:
                warn(f"[Row {i}] invalid split '{split}' (expected train/va/test/reference).")

    return True

# Check labels.jsonl formatting and matching filenames.
def validate_labels(meta_files):
    if not LABELS_PATH.exists():
        warn("labels.jsonl not found (skipping).")
        return True

    line = []
    with open(LABELS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                entry = json.loads(line)
                lines.append(entry)
            except json.JSONDecodeError as e:
                error(f"Invalid JSON: {e}")
                return False

    if not line:
        info("labels.jsonl is empty - nothing to validate yet.")
        return True

    valid = True
    for i, line in enumerate(line, 1):
        fname = None
        if isinstance(line, dict):
            entry = line
        else:
            # try to parse or skip
            try:
                entry = json.loads(line) if isinstance(line, str) else None
            except Exception:
                entry = None
        if not isinstance(entry, dict):
            warn(f"[Line {i}] Skipping non-JSON entry: {line[:40]!r}")
            continue

        fname = entry.get("file")
        if not fname:
            warn(f"[Line {i}] missing 'file' field.")
            valid = False
            continue
        if fname not in meta_files:
            warn(f"[Line {i}] '{fname}' not found in AudioMIX_metadata.csv")
        for fnum in ("energy", "valence"):
            if fnum in entry and not isinstance(entry[fnum], (float, int)):
                warn(f"[Line {i}] field '{fnum}' not numeric: {entry[fnum]}")
    return valid

# Optionally test audio file readability (if soundfile installed)
def validate_audio_files(meta_files):
    if sf is None:
        info("soundfile not installed - skipping audio checks.")
        return True

    valid = True
    for fname in meta_files:
        path = CLIPS_DIR / fname
        if not path.exists():
            warn(f"Missing clip file: {fname}")
            continue
        try:
            with sf.SoundFile(path) as s:
                _ = s.samplerate
        except Exception as e:
            warn(f"Unreadable or corrupt file {fname}: {e}")
            valid = False
    return valid

# Main
def main():
    print ("\n🎧  AudioMIX Dataset Validator\n" + "=" * 40)

    if not DATASET_DIR.exists():
        error("Dataset directory not found: audio/ai/datasets/")
        sys.exit(1)

    all_ok = True

    # Validate metadata
    info("Checking AudioMIX_metadata.csv ...")
    meta_ok = validate_metadata()
    all_ok &= meta_ok

    # Collect file list
    meta_files = []
    if META_PATH.exists():
        try:
            with open(META_PATH, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                meta_files = [r["file"] for r in reader if r.get("file")]
        except Exception:
            pass

    # Validate labels and audio
    info("Checking labels.jsonl ...")
    labels_ok = validate_labels(set(meta_files))
    all_ok &= labels_ok

    info("Checking audio clips ...")
    audio_ok = validate_audio_files(meta_files)
    all_ok &= audio_ok

    print ("\n✅  Validation complete.")
    if all_ok:
        print ("All checks passed! 🎵")
        sys.exit(0)
    else:
        print ("Some issues were found - please review above logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()
