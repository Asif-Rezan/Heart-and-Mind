"""Prepare an original song/video in the cloud without Google account credentials."""
import argparse
import datetime as dt
import gc
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from pipeline import make_song, render, duration, validate_duration, validate_song
from music_cpu import generate
import os


def prepare(run_id, stage='all'):
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
        song = make_song(dt.datetime.now(ZoneInfo('Asia/Dhaka')).date().isoformat(), [], root/'song-draft.json')
        (root/'song.json').write_text(json.dumps(song, ensure_ascii=False, indent=2))
    if stage == 'lyrics':
        print(json.dumps({'phase':'lyrics ready', 'run_id':run_id}), flush=True)
        return
    import lyrics_cpu
    if lyrics_cpu._model is not None:
        lyrics_cpu._model.close()
        lyrics_cpu._model = None
    gc.collect()
    if stage == 'images':
        from song_images import generate_song_images
        generate_song_images(root, song)
        print(json.dumps({'phase': 'images ready', 'run_id': run_id}), flush=True)
        return
    if stage == 'all':
        from song_images import generate_song_images
        generate_song_images(root, song)
        import image_cpu
        image_cpu._pipeline = None
        gc.collect()
    if not (root/'song.wav').exists():
        if stage == 'render':
            raise RuntimeError('Music artifact missing; publishing cannot generate through a remote service')
        generate(song, root/'song.wav', state, save)
    validate_duration(duration(root/'song.wav'))
    if stage == 'music':
        print(json.dumps({'phase':'music ready', 'run_id':run_id}), flush=True)
        return
    if not (root/'video.mp4').exists():
        render(root)
    validate_duration(duration(root/'video.mp4'))
    print(json.dumps({'run_id': run_id, 'phase': 'prepared', 'title': song['title'],
        'duration': duration(root/'video.mp4')}), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--stage', choices=['all', 'lyrics', 'music', 'images', 'render'], default='all')
    args = parser.parse_args()
    prepare(args.run_id, args.stage)
