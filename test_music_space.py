import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import music_space


def api_info(formats=('mp3', 'flac')):
    fields = [('models', 'selected_model', ['acestep-v15-xl-turbo']),
        ('Prompt', 'prompt', None), ('Lyrics', 'lyrics', None),
        ('Vocal Language', 'language', ['hi']), ('Audio Duration (seconds)', 'seconds', None),
        ('Audio Format', 'format', list(formats))]
    return {'named_endpoints': {'/generation_wrapper': {'parameters': [
        {'label': label, 'parameter_name': name, 'type': {'enum': choices} if choices else {}}
        for label, name, choices in fields]}}}


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
