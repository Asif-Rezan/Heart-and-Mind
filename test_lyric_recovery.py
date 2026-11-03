import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from authored_song import load_authored_song
from lyric_quality import LyricQualityError, assess
from lyric_recovery import recover_reviewed_song, ReviewedSongUnavailable
from pipeline import pipeline_failure_message, normalize_lyrics
import prepare_music

IDENTITY = 'ab-baat-karein-2026-11-03'
FIXTURE = Path(__file__).parent/'tests/fixtures/lyrics-editorial-run10.json'


class ReviewedRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.failed = json.loads(FIXTURE.read_text())
        self.song = load_authored_song(IDENTITY)

    def root(self, folder):
        root=Path(folder)/'output'/'saved';root.mkdir(parents=True)
        (root/'song-draft.json').write_text(json.dumps(self.failed['song']))
        (root/'lyrics-quality.json').write_text(json.dumps(self.failed['quality']))
        return root

    def test_real_failed_checkpoint_recovers_without_model_or_rejected_lyrics(self):
        # Real artifact and catalog, no inference/reviewer mocks.
        with tempfile.TemporaryDirectory() as folder:
            root=self.root(folder)
            draft=(root/'song-draft.json').read_bytes()
            report=(root/'lyrics-quality.json').read_bytes()
            recovered=recover_reviewed_song(root,[],'male')
            self.assertNotEqual(recovered['lyrics'],self.failed['song']['lyrics'])
            self.assertEqual(recovered['authored_source']['identity'],IDENTITY)
            self.assertTrue(recovered['lyric_quality']['passed'])
            self.assertEqual(assess(recovered['lyrics'])['warnings'],[])
            self.assertEqual((root/'song-draft.json').read_bytes(),draft)
            self.assertEqual((root/'lyrics-quality.json').read_bytes(),report)
            self.assertEqual(json.loads((root/'lyrics-recovery.json').read_text())['code'],'lyrics_quality_recovered')

    def test_published_lyrics_or_title_are_never_reused(self):
        song=self.song
        for entry in (dict(title=song['title']),dict(hash=hashlib.sha256(normalize_lyrics(song['lyrics']).encode()).hexdigest())):
            with self.subTest(entry=entry),tempfile.TemporaryDirectory() as folder:
                root=self.root(folder)
                with self.assertRaises(ReviewedSongUnavailable):recover_reviewed_song(root,[entry],'male')
                self.assertFalse((root/'lyrics-recovery.json').exists())

    def test_voice_and_existing_media_are_protected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.root(folder)
            with self.assertRaises(ReviewedSongUnavailable):recover_reviewed_song(root,[],'female')
            (root/'song.wav').write_bytes(b'saved')
            with self.assertRaisesRegex(ReviewedSongUnavailable,'Saved media'):recover_reviewed_song(root,[],'male')
            self.assertEqual((root/'song.wav').read_bytes(),b'saved')

    def test_complete_preparation_recovers_after_quality_failure_and_resumes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.root(folder)
            (root/'lyrics-quality.json').unlink()
            store=Mock();store.load.return_value=[]
            with patch('prepare_music.Path',side_effect=lambda x:Path(folder)/x), \
                    patch('storage.Store',return_value=store), \
                    patch('prepare_music.make_song',side_effect=LyricQualityError('rejected')) as model, \
                    patch('prepare_music.generate') as audio:
                prepare_music.prepare('saved','lyrics',check_history=True,motion_video=True)
                prepare_music.prepare('saved','lyrics',check_history=True,motion_video=True)
            self.assertEqual(model.call_count,1)
            audio.assert_not_called()
            saved=json.loads((root/'song.json').read_text())
            self.assertEqual(saved['lyrics'],self.song['lyrics'])
            self.assertEqual(saved['generation_recovery']['mode'],'reviewed-original')
            store.load.assert_called_with('history.json',[])

    def test_restored_run10_rejection_does_not_replay_expensive_model_repairs(self):
        with tempfile.TemporaryDirectory() as folder:
            root=self.root(folder)
            original=(root/'lyrics-quality.json').read_bytes()
            store=Mock();store.load.return_value=[]
            with patch('prepare_music.Path',side_effect=lambda x:Path(folder)/x), \
                    patch('storage.Store',return_value=store), \
                    patch('prepare_music.make_song') as model:
                prepare_music.prepare('saved','lyrics',check_history=True)
            model.assert_not_called()
            self.assertEqual((root/'lyrics-quality.json').read_bytes(),original)
            self.assertEqual(json.loads((root/'song.json').read_text())['authored_source']['identity'],IDENTITY)

    def test_unverified_history_and_unrelated_errors_cannot_trigger_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            self.root(folder)
            for error in (LyricQualityError('rejected'),OSError('runtime')):
                with patch('prepare_music.Path',side_effect=lambda x:Path(folder)/x), \
                        patch('prepare_music.make_song',side_effect=error), \
                        patch('lyric_recovery.recover_reviewed_song') as recovery:
                    with self.assertRaises(type(error)):prepare_music.prepare('saved','lyrics')
                    recovery.assert_not_called()

    def test_review_digest_detects_edited_song_even_when_structure_is_valid(self):
        source=Path(__file__).parent/'lyrics'/f'{IDENTITY}.json'
        record=json.loads(source.read_text());record['song']['description']+=' changed'
        with patch('authored_song.Path.read_bytes',return_value=json.dumps(record).encode()):
            with self.assertRaisesRegex(ValueError,'changed after editorial review'):load_authored_song(IDENTITY)

    def test_exhausted_catalog_has_actionable_safe_error(self):
        message=pipeline_failure_message(ReviewedSongUnavailable('private detail'))
        self.assertIn('reviewed_song_unavailable',message)
        self.assertNotIn('private detail',message)


if __name__ == '__main__':unittest.main()
