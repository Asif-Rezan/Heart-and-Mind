"""Real rejected model output must recover without mocking an editorial approval."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from authored_song import load_authored_song
from lyric_quality import LyricQualityError, assess, parse_sections, section_schema
from lyric_recovery import recover_reviewed_song
from jsonschema import Draft202012Validator
import prepare_music

IDENTITY = 'ek-chhatri-mein-2026-11-04'
FIXTURE = Path(__file__).parent/'tests/fixtures/run14'


class ReviewedRecoveryTests(unittest.TestCase):
    def seed(self, directory):
        root = Path(directory)/'output/music-2026-11-04-new-01'
        root.mkdir(parents=True)
        for name in ('song-draft.json','lyrics-quality.json'):
            (root/name).write_bytes((FIXTURE/name).read_bytes())
        return root

    def test_actual_run14_rejection_recovers_without_another_model_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.seed(directory)
            store = Mock(); store.load.return_value = []
            with patch('prepare_music.Path', side_effect=lambda value:Path(directory)/value), \
                    patch('storage.Store', return_value=store), patch('prepare_music.make_song') as model, \
                    patch('prepare_music.generate') as audio:
                prepare_music.prepare(root.name, 'lyrics', check_history=True, motion_video=True)
            model.assert_not_called(); audio.assert_not_called()
            store.load.assert_called_once_with('history.json', [])
            saved = json.loads((root/'song.json').read_text())
            self.assertEqual(saved['authored_source']['identity'], IDENTITY)
            self.assertTrue(saved['lyric_quality']['passed'])
            self.assertIn('agent editorial review', saved['lyric_quality']['semantic_review']['notes'])
            self.assertNotEqual(saved['lyrics'], json.loads((FIXTURE/'song-draft.json').read_text())['lyrics'])
            for name in ('song-draft.json','lyrics-quality.json'):
                self.assertEqual((root/'rejected-lyrics'/name).read_bytes(), (FIXTURE/name).read_bytes())
            self.assertEqual(json.loads((root/'lyrics-recovery.json').read_text())['strategy'], 'unused-reviewed-song')
            # A subsequent run reuses accepted lyrics, without model rewrites or recovery.
            with patch('prepare_music.Path', side_effect=lambda value:Path(directory)/value), \
                    patch('storage.Store', return_value=store), patch('prepare_music.make_song') as model:
                prepare_music.prepare(root.name, 'lyrics', check_history=True)
            model.assert_not_called()
            self.assertEqual(json.loads((root/'song.json').read_text())['lyrics'], saved['lyrics'])

    def test_fresh_quality_exhaustion_recovers_but_network_failure_does_not(self):
        for error in (LyricQualityError('rejected'), ConnectionError('history/model unavailable')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                store = Mock(); store.load.return_value = []
                with patch('prepare_music.Path', side_effect=lambda value:Path(directory)/value), \
                        patch('storage.Store', return_value=store), patch('prepare_music.make_song', side_effect=error):
                    if isinstance(error, LyricQualityError):
                        prepare_music.prepare('fresh','lyrics',check_history=True,vocal_gender='female')
                        self.assertTrue((Path(directory)/'output/fresh/song.json').exists())
                    else:
                        with self.assertRaises(ConnectionError):
                            prepare_music.prepare('fresh','lyrics',check_history=True,vocal_gender='female')
                        self.assertFalse((Path(directory)/'output/fresh/song.json').exists())

    def test_used_songs_wrong_voice_and_existing_media_cannot_be_selected(self):
        song = load_authored_song(IDENTITY)
        digest = hashlib.sha256(song['lyrics'].encode()).hexdigest()
        for history, voice, media in (([dict(hash=digest)], 'female', None),
                ([dict(title=song['title'])], 'female', None), ([], 'male', None),
                ([], 'female', 'song.wav'), ([], 'female', 'video.mp4')):
            with self.subTest(history=history,voice=voice,media=media), tempfile.TemporaryDirectory() as directory:
                root = self.seed(directory)
                if media: (root/media).write_bytes(b'existing media')
                with self.assertRaises(LyricQualityError):
                    recover_reviewed_song(root, history, voice)
                self.assertFalse((root/'song.json').exists())
                if media: self.assertEqual((root/media).read_bytes(), b'existing media')

    def test_empty_recovery_pool_reports_an_actionable_static_error(self):
        from lyric_quality import LyricRecoveryUnavailable
        from pipeline import pipeline_failure_message
        message = pipeline_failure_message(LyricRecoveryUnavailable('private lyric content'))
        self.assertIn('[lyrics_recovery_unavailable]', message)
        self.assertIn('Add a reviewed original', message)
        self.assertNotIn('private lyric content', message)

    def test_recovery_song_passes_real_structure_and_decoding_contract(self):
        song = load_authored_song(IDENTITY)
        report = assess(song['lyrics'])
        self.assertTrue(report['passed']); self.assertFalse(report['warnings'])
        self.assertTrue(180 <= report['word_count'] <= 220)
        Draft202012Validator(section_schema()).validate(parse_sections(song['lyrics']))
        from music_short import companion
        # Companion lyrics are derived from the accepted parent, never the rejected draft.
        short = companion(song, 'recovery-parent')
        self.assertNotIn('तुम्हारा ट्रेन', short['lyrics'])


if __name__ == '__main__': unittest.main()
