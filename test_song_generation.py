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

    def test_new_run_changes_seed_and_brief_but_retry_keeps_identity(self):
        requests = []
        def request(endpoint, payload):
            requests.append(payload)
            schema = payload['response_format']['json_schema']['schema']
            value = ({k: v for k, v in CORE.items() if k != 'prompt'}
                     if 'lyrics' in schema['properties'] else PACKAGE)
            return response(value)
        with patch('lyrics_cpu.request_story', side_effect=request):
            for identity in ('daily-2026-10-27', 'new-video-01', 'new-video-01'):
                make_song('2026-10-27', [], generation_id=identity)
        first, second, retry = requests[0], requests[2], requests[4]
        self.assertNotEqual(first['seed'], second['seed'])
        self.assertNotEqual(first['messages'], second['messages'])
        self.assertEqual(second, retry)
        self.assertEqual(requests[2]['seed'], requests[3]['seed'])

    def test_reused_title_is_repaired_without_rewriting_lyrics(self):
        history = [{'run': 'previous', 'title': CORE['title'], 'hash': 'different-lyrics'}]
        with tempfile.TemporaryDirectory() as temp:
            draft = Path(temp)/'song-draft.json'
            draft.write_text(json.dumps(CORE))
            with patch('lyrics_cpu.request_story', side_effect=[
                    response({'title': 'सुनहरी राह | Sunehri Raah | Heart Touching Hindi Song 2026'}),
                    response(PACKAGE)]) as request:
                song = make_song('2026-10-27', history, draft, generation_id='new-run')
            self.assertEqual(song['lyrics'], CORE['lyrics'])
            self.assertNotEqual(song['title'], CORE['title'])
            self.assertEqual(request.call_count, 2)
            self.assertEqual(set(request.call_args_list[0].args[1]['response_format']['json_schema']['schema']['properties']), {'title'})
            self.assertIn(song['title'], request.call_args_list[1].args[1]['messages'][-1]['content'])
            self.assertEqual(json.loads(draft.read_text())['title'], song['title'])

    def test_repeated_title_recovery_is_bounded_and_preserves_checkpoint(self):
        from pipeline import DuplicateSongError
        with tempfile.TemporaryDirectory() as temp:
            draft = Path(temp)/'song-draft.json'
            draft.write_text(json.dumps(CORE))
            with patch('lyrics_cpu.request_story', return_value=response({'title': CORE['title']})) as request:
                with self.assertRaises(DuplicateSongError):
                    make_song('2026-10-27', [{'title': CORE['title']}], draft)
            self.assertEqual(request.call_count, 3)
            self.assertEqual(json.loads(draft.read_text())['lyrics'], CORE['lyrics'])

    def test_identical_lyrics_cannot_be_disguised_with_new_title(self):
        import hashlib
        from pipeline import DuplicateSongError
        history = [{'title': 'Other title', 'hash': hashlib.sha256(CORE['lyrics'].encode()).hexdigest()}]
        with tempfile.TemporaryDirectory() as temp:
            draft = Path(temp)/'song-draft.json'
            draft.write_text(json.dumps(CORE))
            with patch('lyrics_cpu.request_story') as request:
                with self.assertRaises(DuplicateSongError):
                    make_song('2026-10-27', history, draft)
            request.assert_not_called()

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
