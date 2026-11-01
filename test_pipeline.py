import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import pipeline


class PipelineTests(unittest.TestCase):
    def test_duplicate_failure_is_actionable_without_leaking_exception_content(self):
        message = pipeline.pipeline_failure_message(pipeline.DuplicateSongError())
        self.assertIn('[duplicate_song]', message)
        self.assertIn('new run ID', message)
        self.assertNotIn('secret-token', pipeline.pipeline_failure_message(RuntimeError('secret-token')))

    def test_duplicate_song_stops_before_upload(self):
        import json
        import tempfile
        store = Mock()
        store.load.side_effect = [{}, [{'title': 'पहले से प्रकाशित', 'hash': 'other'}]]
        song = dict(title='पहले से प्रकाशित', lyrics='हिंदी गीत', prompt='pop',
                    description='Original song', duration=240)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'output' / 'new-run'
            root.mkdir(parents=True)
            (root/'song.json').write_text(json.dumps(song))
            with patch('pipeline.Path', side_effect=lambda value: Path(temp)/value), patch('pipeline.Store', return_value=store), patch('pipeline.youtube_client'):
                with self.assertRaises(pipeline.DuplicateSongError):
                    pipeline.run('new-run')
        store.upload.assert_not_called()
        store.save.assert_not_called()

    def test_duration_boundaries(self):
        for seconds in (180, 240, 360):
            pipeline.validate_duration(seconds)
        for seconds in (0, 179.9, 360.1):
            with self.assertRaises(ValueError):
                pipeline.validate_duration(seconds)

    def test_english_lyrics_rejected(self):
        with self.assertRaises(ValueError):
            pipeline.validate_song(dict(title='Song', lyrics='English only', prompt='pop', description='Music', duration=240))

    def test_ambiguous_upload_not_repeated(self):
        client = Mock()
        with self.assertRaises(RuntimeError):
            pipeline.publish(client, Path('.'), {}, {'upload_started':True}, Mock())
        client.videos.assert_not_called()

    def test_private_video_never_reported_published(self):
        client = Mock()
        client.videos.return_value.list.return_value.execute.return_value = {'items': [{
            'snippet': {'channelId':'expected'}, 'status':{'privacyStatus':'private', 'uploadStatus':'processed'},
            'contentDetails': {'definition':'hd'}}]}
        state = {'video_id':'v', 'thumbnail_uploaded':True}
        with patch.dict('os.environ', {'EXPECTED_CHANNEL_ID':'expected'}):
            with self.assertRaises(RuntimeError):
                pipeline.publish(client, Path('.'), {}, state, Mock())
        self.assertNotEqual(state.get('phase'), 'published')


if __name__ == '__main__':
    unittest.main()


class SafeApiDiagnostics(unittest.TestCase):
    def test_status_and_allowlisted_reason_without_sensitive_body(self):
        error = RuntimeError('secret-token')
        error.resp = type('Response', (), {'status': 403})()
        error.content = b'{"error":{"message":"secret-token","errors":[{"reason":"quotaExceeded"},{"reason":"secret-token"}]}}'
        self.assertEqual(pipeline.safe_api_details(error), {'http_status':403,'reasons':['quotaExceeded']})

    def test_invalid_api_body_is_not_logged(self):
        error = RuntimeError('secret-token')
        error.resp = type('Response', (), {'status':502})()
        error.content = b'secret-token'
        self.assertEqual(pipeline.safe_api_details(error), {'http_status':502,'reasons':[]})
        self.assertEqual(pipeline.safe_api_details(RuntimeError('secret-token')), {})
