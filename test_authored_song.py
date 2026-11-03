import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from authored_song import load_authored_song
from lyric_quality import assess, render_sections, parse_sections
import prepare_music

IDENTITY = 'tum-laut-aao-2026-11-03'


class AuthoredSongTests(unittest.TestCase):
    def test_production_song_is_explicitly_edited_and_has_measured_phrasing(self):
        song = load_authored_song(IDENTITY)
        self.assertEqual(song['lyric_quality']['word_count'],199)
        self.assertTrue(song['lyric_quality']['passed'])
        self.assertFalse(song['lyric_quality']['warnings'])
        self.assertIn('not-model-approval',song['lyric_quality']['semantic_review']['mode'])
        self.assertEqual(song['visual_mood'],'romance')
        self.assertTrue(20<=len(song['prompt'])<=600)
        self.assertTrue(all(40<=len(x)<=160 for x in song['visual_scenes']))

    def test_explicit_authoring_path_never_calls_text_or_audio_generation_in_lyrics_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('prepare_music.Path',side_effect=lambda value:Path(directory)/value),patch('prepare_music.make_song') as model,patch('prepare_music.generate') as audio:
                prepare_music.prepare('authored-new','lyrics',motion_video=True,authored_song=IDENTITY)
            model.assert_not_called();audio.assert_not_called()
            saved=json.loads((Path(directory)/'output/authored-new/song.json').read_text())
            self.assertEqual(saved['lyrics'],load_authored_song(IDENTITY)['lyrics'])
            self.assertTrue(saved['authored_source']['sha256'])

    def test_existing_audio_is_never_relabelled_as_a_different_authored_song(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'output/saved';root.mkdir(parents=True)
            song=load_authored_song(IDENTITY);song['lyrics']=song['lyrics'].replace('तुम लौट आओ','तुम पास आओ')
            (root/'song.json').write_text(json.dumps(song));(root/'song.wav').write_bytes(b'existing-audio')
            with patch('prepare_music.Path',side_effect=lambda value:Path(directory)/value),patch('prepare_music.generate') as audio:
                with self.assertRaisesRegex(ValueError,'fresh run ID'):
                    prepare_music.prepare('saved','music',authored_song=IDENTITY)
            self.assertEqual((root/'song.wav').read_bytes(),b'existing-audio');audio.assert_not_called()

    def test_authored_file_identity_cannot_escape_repository_folder(self):
        for identity in ('../private','/tmp/song','a.json','song;command'):
            with self.assertRaises(ValueError):load_authored_song(identity)

    def test_moderate_written_vowel_mismatch_is_a_warning_not_an_audio_rhythm_failure(self):
        song=load_authored_song(IDENTITY)
        stanzas=parse_sections(song['lyrics'])
        stanzas['bridge']=['मैं तुम्हें नहीं छोड़ूंगा','तुम्हारी आवाज़ बन गई दिल की याद']
        report=assess(render_sections(stanzas))
        self.assertTrue(report['passed'],report['issues'])
        self.assertTrue(any('Bridge' in warning for warning in report['warnings']))


if __name__ == '__main__':unittest.main()
