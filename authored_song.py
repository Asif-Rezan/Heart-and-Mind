"""Load an explicitly selected, repository-reviewed song without text-model rewriting."""
import hashlib
import json
from pathlib import Path
import re

from lyric_quality import VERSION, assess
from pipeline import validate_song


def load_authored_song(identity):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}', identity):
        raise ValueError('Invalid authored song identity')
    folder = (Path(__file__).resolve().parent/'lyrics').resolve()
    source = folder/(identity+'.json')
    if source.is_symlink() or source.resolve().parent != folder:
        raise ValueError('Authored song must be a tracked file in lyrics/')
    data = source.read_bytes()
    record = json.loads(data)
    review = record.get('editorial_review', {})
    if review.get('status') != 'reviewed' or not review.get('reviewer') or not review.get('notes'):
        raise ValueError('Authored song needs an explicit editorial review record')
    song = validate_song(record['song'])
    if song.get('vocal_gender') not in ('male','female'):
        raise ValueError('Authored song must specify its narrator voice')
    report = assess(song['lyrics'])
    if not report['passed']:
        raise ValueError('Authored lyrics failed structural/phrasing checks')
    report['semantic_review'] = dict(passed=True,reviewer=review['reviewer'],
        notes=review['notes'],mode='repository-authored-editorial-review-not-model-approval')
    song['lyric_quality_version'] = VERSION
    song['lyric_quality'] = report
    song['authored_source'] = dict(identity=identity,sha256=hashlib.sha256(data).hexdigest())
    return song
