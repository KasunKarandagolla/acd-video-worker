#!/usr/bin/env python3
"""Run FFmpeg loudnorm measurement and emit an audio_loudness_measurement JSON record."""
import json, re, subprocess, sys
from pathlib import Path
if len(sys.argv)<2:
    print('Usage: ffmpeg_loudness_check.py <audio-or-video-file>', file=sys.stderr)
    sys.exit(2)
path=Path(sys.argv[1])
if not path.exists():
    print(f'ERROR: missing file: {path}', file=sys.stderr)
    sys.exit(1)
cmd=['ffmpeg','-hide_banner','-nostats','-i',str(path),'-af','loudnorm=I=-14:TP=-1:LRA=11:print_format=json','-f','null','-']
proc=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
combined=proc.stdout+'\n'+proc.stderr
match=re.search(r'\{\s*"input_i".*?\}', combined, re.S)
if not match:
    print(json.dumps({'measured_by':'ffmpeg_loudnorm','pass':False,'error':'loudnorm JSON not found','returncode':proc.returncode}, indent=2))
    sys.exit(1)
data=json.loads(match.group(0))
integrated=float(data.get('input_i','nan'))
tp=float(data.get('input_tp','nan'))
record={
  'audio_loudness_measurement': {
    'measured_by':'ffmpeg_loudnorm',
    'integrated_lufs': integrated,
    'true_peak_db': tp,
    'loudness_range_lra': float(data.get('input_lra','nan')),
    'pass': integrated <= -13.0 and integrated >= -15.5 and tp <= -1.0,
    'correction_needed': not (integrated <= -13.0 and integrated >= -15.5 and tp <= -1.0),
    'suggested_filter': 'loudnorm=I=-14:TP=-1:LRA=11'
  }
}
print(json.dumps(record, indent=2))
sys.exit(0 if record['audio_loudness_measurement']['pass'] else 1)
