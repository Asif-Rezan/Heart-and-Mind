"""Prepare an original song/video in the cloud without Google account credentials."""
import argparse
import datetime as dt
import gc
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from pipeline import make_song, render, duration, validate_duration, AceStep, validate_song
from music_space import generate
import os


def prepare(run_id):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id):
        raise ValueError('Invalid run ID')
    root = Path('output')/run_id
    root.mkdir(parents=True, exist_ok=True)
    checkpoint = root/'generation-state.json'
    state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
    def save():
        temporary = checkpoint.with_suffix('.tmp')
        temporary.write_text(json.dumps(state))
        temporary.replace(checkpoint)
    if (root/'song.json').exists():
        song = validate_song(json.loads((root/'song.json').read_text()))
    else:
        song = make_song(dt.datetime.now(ZoneInfo('Asia/Dhaka')).date().isoformat(), [])
        (root/'song.json').write_text(json.dumps(song, ensure_ascii=False, indent=2))
    import lyrics_cpu
    lyrics_cpu._model = None
    gc.collect()
    if not (root/'song.wav').exists():
        if os.getenv('ACESTEP_API_URL'):
            AceStep().generate(song, state, save, root/'song.wav')
        else:
            generate(song, root/'song.wav', state, save)
    validate_duration(duration(root/'song.wav'))
    render(root)
    print(json.dumps({'run_id': run_id, 'phase': 'prepared', 'title': song['title'],
        'duration': duration(root/'video.mp4')}), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    prepare(args.run_id)
