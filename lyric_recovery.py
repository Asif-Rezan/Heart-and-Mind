"""Bounded recovery from rejected drafts using opted-in, reviewed originals."""
import json
from pathlib import Path

from authored_song import load_authored_song
from pipeline import song_duplicate_reason
from lyric_quality import LyricQualityError


class ReviewedSongUnavailable(LyricQualityError):
    """No suitable unpublished reviewed original remains in the recovery catalog."""


def recover_reviewed_song(root, history, voice):
    root = Path(root)
    # Changing lyrics after any audio/video exists would mislabel saved media.
    if any(root.glob('*.wav')) or any(root.glob('*.mp4')):
        raise ReviewedSongUnavailable('Saved media exists; lyric replacement is forbidden')
    catalog = Path(__file__).resolve().parent/'lyrics'
    candidates = []
    for source in sorted(catalog.glob('*.json')):
        # Historical authored songs require explicit selection. Only records whose
        # author opted into automatic recovery and bound their review are eligible.
        if source.is_symlink():continue
        try:
            record = json.loads(source.read_text())
        except (ValueError, OSError):
            continue
        if not isinstance(record,dict):continue
        if record.get('automatic_recovery') is not True:
            continue
        review=record.get('editorial_review')
        if not isinstance(review,dict) or not review.get('song_sha256'):
            continue
        try:
            song = load_authored_song(source.stem)
        except (ValueError, KeyError, TypeError):
            continue
        if song['vocal_gender'] == voice and not song_duplicate_reason(song, history):
            candidates.append(song)
    if not candidates:
        raise ReviewedSongUnavailable('No unpublished reviewed song matches the requested voice; '
                                      'add a reviewed original to lyrics/ or explicitly choose authored_song')
    song = candidates[0]
    journal = dict(code='lyrics_quality_recovered', mode='reviewed-original',
                   authored_source=song['authored_source'], voice=voice,
                   rejected_draft='song-draft.json', rejected_report='lyrics-quality.json',
                   music_started=False)
    temporary = root/'lyrics-recovery.tmp'
    temporary.write_text(json.dumps(journal,ensure_ascii=False,indent=2))
    temporary.replace(root/'lyrics-recovery.json')
    song['generation_recovery'] = journal
    print(json.dumps(dict(phase='lyrics quality recovered',mode=journal['mode'],
                          identity=song['authored_source']['identity'])),flush=True)
    return song
