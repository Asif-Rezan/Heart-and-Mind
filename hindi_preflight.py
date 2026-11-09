"""Validate a real Hindi episode with the production CPU writer, without publication."""
import argparse
import json
from pathlib import Path
from prepare_music import prepare_with_retries
from hindi import validate_song_language, require_hindi
from episode_packaging import validate_package, public_metadata
from song_images import image_plan


def run(run_id):
    prepare_with_retries(run_id, 'lyrics', check_history=False, vocal_gender='female')
    root = Path('output') / run_id
    song = json.loads((root / 'song.json').read_text())
    validate_song_language(song)
    validate_package(song['packaging'], song)
    assert song['duration'] == 240 and len(song['scenes']) == 48
    assert [s['section'] for s in song['scenes'][:4]] == ['chorus'] * 4
    assert image_plan(song)[-1]['reference_scene'] == 'scene-000'
    for kind in ('video', 'shorts'):
        meta = public_metadata(song, kind)
        require_hindi(meta['title'], kind+' title')
        require_hindi(meta['description'], kind+' description')
    summary = dict(passed=True, language='hi', seconds=240, scenes=48,
                   real_cpu_model=True, reference_form=True, uploads_performed=False)
    (root / 'hindi-validation.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    run(parser.parse_args().run_id)
