"""Regression coverage from the rejected draft in production run 41773674684."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator, ValidationError
import lyrics_cpu
from lyric_quality import assess, parse_sections, section_schema
from pipeline import make_song
from test_song_generation import CORE, PACKAGE, response

FIXTURE = Path(__file__).parent / 'tests/fixtures/run13'


class LyricLineRecoveryTests(unittest.TestCase):
    def test_actual_failed_line_is_rejected_at_generation_boundary(self):
        song = json.loads((FIXTURE / 'song-draft.json').read_text())
        report = assess(song['lyrics'])
        self.assertEqual(report['issues'], ['Verse 2 line 2: 11 words; use 4-10 words, aim 6-9'])
        with self.assertRaises(ValidationError) as caught:
            Draft202012Validator(section_schema()).validate(parse_sections(song['lyrics']))
        self.assertEqual(list(caught.exception.absolute_path), ['verse_2', 1])

    def test_decoder_keeps_word_grammar_and_retries_the_specific_line(self):
        broken = json.loads((FIXTURE / 'song-draft.json').read_text())
        outputs = [response(broken), response(CORE)]
        prompts = []
        def generate(**kwargs):
            prompts.append(copy.deepcopy(kwargs))
            return outputs.pop(0)
        model = Mock(tokenize=Mock(return_value=[1]), create_chat_completion=Mock(side_effect=generate))
        payload = dict(model=lyrics_cpu.MODEL_ID, messages=[dict(role='user', content='Write lyrics')],
            max_completion_tokens=1000, seed=100,
            response_format=dict(type='json_schema', json_schema=dict(schema=dict(type='object',
                properties=dict(title=dict(type='string'), duration=dict(type='number'), lyrics=section_schema()),
                required=['lyrics','title','duration']))))
        with patch.object(lyrics_cpu, 'load_model', return_value=model):
            result = lyrics_cpu.request_story('chat/completions', payload)
        self.assertEqual(json.loads(result['choices'][0]['message']['content'])['lyrics'], parse_sections(CORE['lyrics']))
        grammar = prompts[0]['response_format']['schema']['properties']['lyrics']['properties']['verse_2']['items']
        self.assertEqual(grammar['pattern'], section_schema()['properties']['verse_2']['items']['pattern'])
        self.assertIn('lyrics.verse_2.1', prompts[1]['messages'][-1]['content'])
        self.assertIn('Shorten overloaded lines', prompts[1]['messages'][-1]['content'])
        self.assertEqual([p['seed'] for p in prompts], [100, 101])

    def test_native_schema_compiles_without_unbounded_unicode_rules(self):
        try:
            from llama_cpp import LlamaGrammar
        except ImportError:
            self.skipTest('Native decoder runtime is exercised in the GitHub lyrics job')
        schema = section_schema()
        # request_story removes string lengths before sending the native grammar.
        for stanza in schema['properties'].values():
            stanza['items'].pop('minLength')
            stanza['items'].pop('maxLength')
        self.assertIsNotNone(LlamaGrammar.from_json_schema(json.dumps(schema), verbose=False))

    def test_actual_saved_rejection_recovers_and_then_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory) / 'song-draft.json'
            for name in ('song-draft.json', 'lyrics-quality.json'):
                (draft.parent/name).write_bytes((FIXTURE/name).read_bytes())
            with patch('lyrics_cpu.request_story', side_effect=[response({'lyrics':CORE['lyrics']}), response(PACKAGE)]) as model, \
                    patch('lyric_quality.review', return_value=dict(passed=True,issues=[])) as critic:
                song = make_song('2026-11-04', [], draft, generation_id='music-2026-11-04-new-01')
            self.assertEqual(model.call_count, 2)
            critic.assert_called_once()
            self.assertIn('Verse 2 line 2: 11 words', model.call_args_list[0].args[1]['messages'][-1]['content'])
            self.assertTrue(song['lyric_quality']['passed'])
            self.assertTrue(json.loads((draft.parent/'lyrics-quality.json').read_text())['passed'])
            self.assertEqual(song['vocal_gender'], 'female')


if __name__ == '__main__':
    unittest.main()
