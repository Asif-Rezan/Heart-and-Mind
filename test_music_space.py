import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import music_space


def api_info(formats=('mp3', 'flac')):
    fields = [('models', 'selected_model', ['acestep-v15-turbo']),
        ('Prompt', 'prompt', None), ('Lyrics', 'lyrics', None),
        ('Vocal Language', 'language', ['hi']), ('Audio Duration (seconds)', 'seconds', None),
        ('Audio Format', 'format', list(formats)), ('Thinking', 'thinking', None)]
    parameters = [
        {'label': label, 'parameter_name': name, 'type': {'enum': choices} if choices else {}}
        for label, name, choices in fields]
    parameters += [{'label':'planning', 'parameter_name':name, 'type':{'type':'boolean'}, 'parameter_default':True}
        for name in ('param_37', 'param_38', 'param_39')]
    return {'named_endpoints': {'/generation_wrapper': {'parameters': parameters}}}


class SpaceTests(unittest.TestCase):
    def test_flac_requested_and_converted_to_real_wav_path_before_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root/'result.flac'
            audio.write_bytes(b'FLAC source')
            target = root/'song.wav'
            client = Mock()
            client.view_api.return_value = api_info()
            client.predict.return_value = [str(audio)]
            snapshots = []
            state = {}
            def convert(args, **kwargs):
                self.assertEqual(args[args.index('-c:a') + 1], 'pcm_s16le')
                Path(args[-1]).write_bytes(b'RIFF converted WAV')
            with patch.object(music_space, 'Client', return_value=client), patch('pipeline.duration', return_value=240), patch.object(music_space.subprocess, 'run', side_effect=convert):
                music_space.generate({'prompt':'Hindi pop', 'lyrics':'तेरी याद', 'duration':240}, target, state,
                    lambda: snapshots.append(copy.deepcopy(state)))
            self.assertEqual(client.predict.call_args.kwargs['format'], 'flac')
            self.assertTrue(target.read_bytes().startswith(b'RIFF'))
            self.assertFalse(snapshots[0].get('audio_ready', False))
            self.assertTrue(state['audio_ready'])

    def test_unsupported_format_rejected_before_submission_checkpoint(self):
        client = Mock()
        client.view_api.return_value = api_info(('mp3',))
        state = {}
        save = Mock()
        with patch.object(music_space, 'Client', return_value=client):
            with self.assertRaisesRegex(RuntimeError, 'Audio Format'):
                music_space.generate({'prompt':'pop', 'lyrics':'हिंदी', 'duration':240}, Path('song.wav'), state, save)
        client.predict.assert_not_called()
        save.assert_not_called()
        self.assertFalse(state.get('generation_started', False))

    def test_ambiguous_submission_cannot_be_silently_retried(self):
        with patch.object(music_space, 'Client') as client:
            with self.assertRaisesRegex(RuntimeError, 'Ambiguous'):
                music_space.generate({}, Path('song.wav'), {'generation_started':True}, Mock())
        client.assert_not_called()

    def test_smaller_turbo_and_all_planning_passes_disabled(self):
        client = Mock()
        client.view_api.return_value = api_info()
        client.predict.return_value = [None]
        with patch.object(music_space, 'Client', return_value=client):
            with self.assertRaisesRegex(RuntimeError, 'no generated audio'):
                music_space.generate({'prompt':'pop', 'lyrics':'हिंदी', 'duration':240}, Path('song.wav'), {}, Mock())
        values = client.predict.call_args.kwargs
        self.assertEqual(values['selected_model'], 'acestep-v15-turbo')
        for name in ('thinking', 'param_37', 'param_38', 'param_39'):
            self.assertIs(values[name], False)

    def test_terminal_gpu_abort_is_resumable_but_timeout_remains_ambiguous(self):
        from gradio_client.exceptions import AppError
        for error, expected_started in ((AppError('GPU task aborted'), False), (TimeoutError('network timeout'), True)):
            client = Mock()
            client.view_api.return_value = api_info()
            client.predict.side_effect = error
            state = {}
            with patch.object(music_space, 'Client', return_value=client):
                with self.assertRaises((RuntimeError, TimeoutError)):
                    music_space.generate({'prompt':'pop', 'lyrics':'हिंदी', 'duration':240}, Path('song.wav'), state, Mock())
            self.assertEqual(state['generation_started'], expected_started)

    def test_hugging_face_token_is_passed_to_music_client(self):
        client = Mock()
        client.view_api.return_value = api_info()
        client.predict.return_value = [None]
        with patch.dict('os.environ', {'HF_TOKEN': 'test-only-token'}), patch.object(music_space, 'Client', return_value=client) as factory:
            with self.assertRaisesRegex(RuntimeError, 'no generated audio'):
                music_space.generate({'prompt':'pop', 'lyrics':'हिंदी', 'duration':240}, Path('song.wav'), {}, Mock())
        self.assertEqual(factory.call_args.kwargs['token'], 'test-only-token')

    def test_confirmed_quota_rejection_is_saved_without_blind_retries(self):
        from gradio_client.exceptions import AppError
        client = Mock()
        client.view_api.return_value = api_info()
        client.predict.side_effect = AppError('You have exceeded your ZeroGPU runs limit. Authenticate with a Hugging Face token for more quota')
        state = {}
        with patch.object(music_space, 'Client', return_value=client):
            with self.assertRaisesRegex(RuntimeError, 'configure HF_TOKEN'):
                music_space.generate({'prompt':'pop', 'lyrics':'हिंदी', 'duration':240}, Path('song.wav'), state, Mock())
        self.assertFalse(state['generation_started'])
        self.assertIn('quota', state['generation_failed'])
        self.assertEqual(client.predict.call_count, 1)
