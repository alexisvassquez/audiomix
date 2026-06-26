# audiomix
# AudioMIX
# audio/eq/eq_send_preset.py

"""
Instructions:

- Run using commands:
    mkfifo /tmp/audiomix_ctl
    ./build/audiomix --headless < /tmp/audiomix_ctl

- In a separate terminal, run:
    python3 eq_send_preset.py --preset bass_boost > /tmp/audiomix_ctl

- AudioMIX DSP system will send an acknowledgment back:
    {"cmd":"ack", "ack":"eq.set"}
"""

import argparse
import json
import os
import sys
import signal
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def load_presets(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def preset_to_eq_set(preset: dict, sample_rate: int, preamp_db: float) -> dict:
    filters = preset.get("filters", [])
    bands = []
    for f in filters:
        bands.append({
            "type": "peaking",
            "f0": float(f["freq"]),
            "q": float(f.get("q", 1.0)),
            "gain_db": float(f.get("gain_db", 0.0)),
            "enabled": True
        })

    return {
        "cmd": "eq.set",
        "payload": {
            "sample_rate": int(sample_rate),
            "preamp_db": float(preamp_db),
            "bands": bands
        }
    }

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_presets = os.path.join(script_dir, "presets", "presets_combined.json")
    ap = argparse.ArgumentParser(description="Emit AudioMIX eq.set JSON from presets_combined.json")
    ap.add_argument("--presets", default=default_presets,
                    help="Path to presets_combined.json")
    ap.add_argument("--preset", required=True,
                    help="Preset name (key in presets JSON), e.g. bass_boost")
    ap.add_argument("--sample-rate", type=int, default=44100)    # 44.1 kHz
    ap.add_argument("--preamp-db", type=float, default=0.0,
                    help="Optional preamp attenuation to reduce clipping risk (e.g. -3.0)")
    ap.add_argument("--list", action="store_true", help="List available presets and exit")

    args = ap.parse_args()
    presets = load_presets(args.presets)

    if args.list:
        for k in sorted(presets.keys()):
            print (k)
        return 0

    if args.preset not in presets:
        print (f'{{"cmd":"error","error":"unknown_preset","name":"{args.preset}"}}', file=sys.stderr)
        print ("Available:", ", ".join(sorted(presets.keys())), file=sys.stderr)
        return 2

    msg = preset_to_eq_set(presets[args.preset], args.sample_rate, args.preamp_db)
    try:
        print (json.dumps(msg), flush=True)
    except BrokenPipeError:
        return 0

if __name__ == "__main__":
    raise SystemExit(main())

