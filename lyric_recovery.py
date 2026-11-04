"""Recover rejected text with an explicitly reviewed, unused repository song."""
import json
from pathlib import Path
import shutil

from authored_song import load_authored_song
from lyric_quality import LyricQualityError, LyricRecoveryUnavailable
from pipeline import song_duplicate_reason

CATALOG = Path(__file__).resolve().parent / 'lyrics'


def recover_reviewed_song(root, history, voice):
    # Changing lyrics underneath synthesized media would corrupt the checkpoint.
    if any(root.rglob('*.wav')) or any(root.rglob('*.mp4')):
        raise LyricQualityError('Cannot replace rejected lyrics with existing audio/video')
    for path in sorted(CATALOG.glob('*.json')):
        record = json.loads(path.read_text())
        if record.get('recovery_eligible') is not True:
            continue
        song = load_authored_song(path.stem)
        if song['vocal_gender'] != voice or song_duplicate_reason(song, history):
            continue
        rejected = root / 'rejected-lyrics'
        rejected.mkdir(exist_ok=True)
        for name in ('song-draft.json', 'lyrics-quality.json'):
            if (root/name).exists():
                shutil.copy2(root/name, rejected/name)
        # Record provenance before the caller writes the accepted song checkpoint.
        details = dict(reason='lyrics_quality_rejected', strategy='unused-reviewed-song',
                       source=song['authored_source'], vocal_gender=voice)
        temporary = root/'lyrics-recovery.tmp'
        temporary.write_text(json.dumps(details, indent=2))
        temporary.replace(root/'lyrics-recovery.json')
        print(json.dumps(dict(phase='lyrics quality recovered', strategy=details['strategy'],
                              identity=path.stem)), flush=True)
        return song
    raise LyricRecoveryUnavailable('No unused reviewed song for the requested voice is available')


def rejected_checkpoint(root):
    """A saved failed semantic critique may recover without repeating the same model loop."""
    path = root/'lyrics-quality.json'
    if not path.exists():
        return False
    quality = json.loads(path.read_text())
    return (quality.get('passed') is False and
            (quality.get('attempts_exhausted') is True or
             quality.get('semantic_review', {}).get('passed') is False))
