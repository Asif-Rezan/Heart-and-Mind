import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator

from pipeline import make_song

CORE = {'title': 'नई सुबह | Nayi Subah | Hindi Soulful Song', 'lyrics': '[Verse 1]\n' + 'नई सुबह में फिर से जीना है\n'*30,
        'prompt': 'Hindi cinematic soulful pop with piano and warm expressive vocals', 'duration': 240}
PACKAGE = {'description': 'A hopeful original Hindi song about starting again. #HindiMusic',
           'tags': ['Nayi Subah', 'नई सुबह', 'Hindi song', 'Hindi soul', 'hopeful song', 'Hindi pop', 'original music', 'Heart and Mind'],
           'thumbnail_text': 'NAYI SUBAH',
           'background_prompt': 'An adult South Asian woman in a meadow watches the sunrise, hopeful expression, cinematic warm golden light.',
           'thumbnail_prompt': 'Close portrait of a hopeful South Asian adult, glowing sunrise on the right, dark empty left, cinematic photography.'}


def response(value):
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]}


class SongGenerationTests(unittest.TestCase):
    def test_song_and_packaging_are_separate_validated_requests(self):
        requests = []
        def request(endpoint, payload):
            schema = payload['response_format']['json_schema']['schema']
            value = {k: v for k, v in CORE.items() if k != 'prompt'} if 'lyrics' in schema['properties'] else PACKAGE
            Draft202012Validator(schema).validate(value)
            requests.append(payload)
            return response(value)
        with patch('lyrics_cpu.request_story', side_effect=request):
            song = make_song('2026-10-26', [])
        self.assertEqual(len(requests), 2)
        self.assertEqual(song['lyrics'], CORE['lyrics'])
        self.assertEqual(song['thumbnail_prompt'], PACKAGE['thumbnail_prompt'])
        self.assertNotIn('prompt', requests[0]['response_format']['json_schema']['schema']['properties'])
        self.assertTrue(20 <= len(song['prompt']) <= 600)
        self.assertNotIn('tags', requests[0]['response_format']['json_schema']['schema']['properties'])
        self.assertNotIn('lyrics', requests[1]['response_format']['json_schema']['schema']['properties'])
        self.assertIn(CORE['title'], requests[1]['messages'][-1]['content'])
        self.assertLess(requests[1]['max_completion_tokens'], requests[0]['max_completion_tokens'])

    def test_valid_lyrics_survive_packaging_failure_and_are_not_regenerated(self):
        with tempfile.TemporaryDirectory() as temp:
            draft = Path(temp)/'song-draft.json'
            with patch('lyrics_cpu.request_story', side_effect=[response(CORE), RuntimeError('interrupted')]):
                with self.assertRaises(RuntimeError):
                    make_song('2026-10-26', [], draft)
            saved = json.loads(draft.read_text())
            self.assertEqual(saved['lyrics'], CORE['lyrics'])
            self.assertTrue(20 <= len(saved['prompt']) <= 600)
            with patch('lyrics_cpu.request_story', return_value=response(PACKAGE)) as request:
                song = make_song('2026-10-26', [], draft)
            request.assert_called_once()
            self.assertEqual(song['lyrics'], CORE['lyrics'])

    def test_every_daily_style_uses_bounded_directions_without_generated_prose(self):
        import datetime as dt
        prompts = set()
        for offset in range(8):
            day = (dt.date(2026, 10, 27) + dt.timedelta(days=offset)).isoformat()
            def request(endpoint, payload):
                schema = payload['response_format']['json_schema']['schema']
                value = ({k: v for k, v in CORE.items() if k != 'prompt'}
                         if 'lyrics' in schema['properties'] else PACKAGE)
                Draft202012Validator(schema).validate(value)
                return response(value)
            with patch('lyrics_cpu.request_story', side_effect=request):
                song = make_song(day, [])
            self.assertTrue(20 <= len(song['prompt']) <= 600)
            self.assertIn('Clear Hindi diction', song['prompt'])
            prompts.add(song['prompt'])
        self.assertEqual(len(prompts), 8)

    def test_retry_reports_field_and_constraint_without_quoting_generated_content(self):
        import lyrics_cpu
        from unittest.mock import Mock
        payload = {'model': lyrics_cpu.MODEL_ID, 'messages': [{'role': 'user', 'content': 'write'}],
                   'response_format': {'json_schema': {'schema': {'type': 'object', 'properties': {
                       'thumbnail_text': {'type': 'string', 'maxLength': 5}}, 'required': ['thumbnail_text']}}},
                   'max_completion_tokens': 256}
        result = response({'thumbnail_text': 'private generated content'})
        model = Mock(tokenize=Mock(return_value=[1]), create_chat_completion=Mock(return_value=result))
        with patch('lyrics_cpu.load_model', return_value=model), patch('builtins.print') as output:
            with self.assertRaises(lyrics_cpu.StoryGenerationError):
                lyrics_cpu.request_story('chat/completions', payload)
        logs = str(output.call_args_list)
        self.assertIn('maxLength', logs)
        self.assertIn('thumbnail_text', logs)
        self.assertNotIn('private generated content', logs)
        feedback = model.create_chat_completion.call_args.kwargs['messages'][-1]['content']
        self.assertIn('maxLength is 5', feedback)


if __name__ == '__main__':
    unittest.main()
