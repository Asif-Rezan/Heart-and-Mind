"""Regression coverage for real failure 41824183925: 153 words and exhausted pool."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator, ValidationError
from authored_song import load_authored_song
from lyric_quality import (assess, generation_section_schema, parse_sections,
                           render_sections, SECTION_KEYS)
from lyric_recovery import recover_reviewed_song
import prepare_music

FIXTURE = Path(__file__).parent/'tests/fixtures/run41824183925'
IDENTITY = 'kitabon-ke-beech-2026-11-04'


class LyricBudgetRecoveryTests(unittest.TestCase):
    def seed(self, folder):
        root=Path(folder)/'output'/'natural-storybook-20261104-1751'
        root.mkdir(parents=True)
        for name in ('song-draft.json','lyrics-quality.json'):
            (root/name).write_bytes((FIXTURE/name).read_bytes())
        return root

    def test_real_153_word_response_cannot_pass_new_decoder_schema(self):
        song=json.loads((FIXTURE/'song-draft.json').read_text())
        self.assertEqual(assess(song['lyrics'])['word_count'],153)
        with self.assertRaises(ValidationError):
            Draft202012Validator(generation_section_schema()).validate(parse_sections(song['lyrics']))

    def test_shortest_and_longest_decodable_songs_have_valid_total_word_budget(self):
        schema=generation_section_schema()
        for longest,expected in ((False,182),(True,220)):
            sections={}
            for index,(key,count) in enumerate(SECTION_KEYS):
                words=(9 if key=='chorus' else 8) if longest else 7
                sections[key]=[' '.join(['शब्द']*(words-1)+[f'पंक्ति'+chr(0x0915+index*4+i)]) for i in range(count)]
            Draft202012Validator(schema).validate(sections)
            report=assess(render_sections(sections))
            self.assertEqual(report['word_count'],expected)
            self.assertFalse(any('Total sung words' in issue for issue in report['issues']))

    def test_exact_failed_run_recovers_without_regenerating_or_changing_voice(self):
        # Consume the previous reserve: this was the missing case in the failed run.
        previous=load_authored_song('ek-chhatri-mein-2026-11-04')
        history=[dict(hash=hashlib.sha256(previous['lyrics'].encode()).hexdigest())]
        with tempfile.TemporaryDirectory() as folder:
            root=self.seed(folder)
            store=Mock();store.load.return_value=history
            with patch('prepare_music.Path',side_effect=lambda value:Path(folder)/value),patch('storage.Store',return_value=store),patch('prepare_music.make_song') as model,patch('prepare_music.generate') as audio:
                prepare_music.prepare(root.name,'lyrics',check_history=True,motion_video=True)
            model.assert_not_called();audio.assert_not_called()
            saved=json.loads((root/'song.json').read_text())
            self.assertEqual(saved['authored_source']['identity'],IDENTITY)
            self.assertEqual(saved['vocal_gender'],'female')
            self.assertEqual(saved['lyric_quality']['word_count'],184)
            self.assertTrue(saved['lyric_quality']['passed'])
            self.assertEqual((root/'rejected-lyrics/song-draft.json').read_bytes(),(FIXTURE/'song-draft.json').read_bytes())

    def test_exhausted_catalogue_attempts_bounded_draft_repair_instead_of_stopping(self):
        accepted=load_authored_song(IDENTITY)
        with tempfile.TemporaryDirectory() as folder:
            root=self.seed(folder)
            catalogue=Path(folder)/'empty';catalogue.mkdir()
            store=Mock();store.load.return_value=[]
            with patch('prepare_music.Path',side_effect=lambda value:Path(folder)/value),patch('storage.Store',return_value=store),patch('lyric_recovery.CATALOG',catalogue),patch('prepare_music.make_song',return_value=accepted) as repair:
                prepare_music.prepare(root.name,'lyrics',check_history=True)
            repair.assert_called_once()
            self.assertEqual(repair.call_args.args[2],root/'song-draft.json')
            self.assertTrue((root/'song.json').exists())

    def test_used_new_reserve_cannot_be_selected_again(self):
        song=load_authored_song(IDENTITY)
        other=load_authored_song('ek-chhatri-mein-2026-11-04')
        history=[dict(hash=hashlib.sha256(s['lyrics'].encode()).hexdigest()) for s in (song,other)]
        from lyric_quality import LyricRecoveryUnavailable
        with tempfile.TemporaryDirectory() as folder:
            root=self.seed(folder)
            with self.assertRaises(LyricRecoveryUnavailable):
                recover_reviewed_song(root,history,'female')

    def test_native_decoder_compiles_the_stricter_word_budget(self):
        try:
            from llama_cpp import LlamaGrammar
        except ImportError:
            self.skipTest('Native grammar runs in the Python 3.12 lyrics job')
        schema=generation_section_schema()
        for stanza in schema['properties'].values():
            stanza['items'].pop('minLength')
            stanza['items'].pop('maxLength')
        self.assertIsNotNone(LlamaGrammar.from_json_schema(json.dumps(schema),verbose=False))

    def test_failure_diagnostics_do_not_leak_model_output_and_explain_resume(self):
        import music_failure
        from lyric_quality import LyricRecoveryUnavailable
        with tempfile.TemporaryDirectory() as folder:
            root=self.seed(folder)
            with patch('music_failure.Path',side_effect=lambda value:Path(folder)/value):
                report=music_failure.save_failure(root.name,'lyrics',LyricRecoveryUnavailable('private draft and token'))
            self.assertEqual(report['lyric_word_count'],153)
            self.assertEqual(report['code'],'lyrics_recovery_unavailable')
            self.assertFalse(report['has_audio'])
            self.assertIn('prepared_run',report['resume'])
            self.assertNotIn('private draft',json.dumps(report))
            self.assertTrue((root/'generation-failure.json').exists())

    def test_invalid_model_json_can_recover_but_runtime_errors_are_not_hidden(self):
        from lyrics_cpu import StoryGenerationError
        for code in ('story_model_response_invalid','story_model_runtime_failure'):
            with self.subTest(code=code),tempfile.TemporaryDirectory() as folder:
                store=Mock();store.load.return_value=[]
                with patch('prepare_music.Path',side_effect=lambda value:Path(folder)/value),patch('storage.Store',return_value=store),patch('prepare_music.make_song',side_effect=StoryGenerationError('private output',code=code)):
                    if code=='story_model_response_invalid':
                        prepare_music.prepare('new','lyrics',check_history=True,vocal_gender='female')
                        self.assertTrue((Path(folder)/'output/new/song.json').exists())
                    else:
                        with self.assertRaises(StoryGenerationError):
                            prepare_music.prepare('new','lyrics',check_history=True,vocal_gender='female')
                        self.assertFalse((Path(folder)/'output/new/song.json').exists())
