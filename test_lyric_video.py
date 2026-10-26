import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from PIL import Image

import image_cpu
from lyric_video import timed_shots, validate_plan, generate_shard
from pipeline import metadata_tags, song_profile, SONG_PROFILES, validate_song, optimize_metadata, publish

WORDS = ['तेरी', 'आँखों', 'मेरे', 'सपने', 'प्यार', 'नदी', 'बारिश', 'आसमान', 'राह', 'हवा']*12
LYRICS = ' '.join(WORDS)
TIMED = [dict(start=i*1.5, end=i*1.5+1, word=word) for i, word in enumerate(WORDS)]
SONG = dict(title='नई सुबह', romanized_title='Nayi Subah', lyrics=LYRICS,
            prompt='Hindi album song with warm vocals and acoustic guitar', description='A story of hope and love.',
            duration=240, visual_mood='healing', tags=['Hindi album song', 'हिंदी गाना'],
            thumbnail_text='NAYI SUBAH', thumbnail_prompt='Hopeful adult Indian woman watching sunrise, cinematic close-up on right, empty dark left.')


def plan(seconds=180):
    shots = timed_shots(LYRICS, TIMED, seconds)
    for shot in shots:
        shot['prompt'] = 'An adult Indian couple walking by a river in warm cinematic light, a different angle.'
    return dict(identity='identity', audio_hash='audio', duration=seconds, complete=True, shots=shots)


class LyricVideoTests(unittest.TestCase):
    def test_five_second_shots_cover_complete_audio_and_use_vocal_context(self):
        shots = timed_shots(LYRICS, TIMED, 181.7)
        self.assertEqual(len(shots), 37)
        self.assertEqual([s['start'] for s in shots], list(range(0, 185, 5)))
        self.assertAlmostEqual(shots[-1]['duration'], 1.7)
        self.assertAlmostEqual(sum(s['duration'] for s in shots), 181.7)
        self.assertIn('आँखों', shots[0]['lyrics'])
        self.assertNotEqual(shots[0]['lyrics'], shots[1]['lyrics'])

    def test_no_guessed_alignment_when_vocals_do_not_match_lyrics(self):
        with self.assertRaisesRegex(RuntimeError, 'reliably timed'):
            timed_shots(LYRICS, [dict(start=0, end=1, word='अलगबात')], 180)

    def test_invalid_or_incomplete_timeline_is_rejected(self):
        original = plan()
        validate_plan(original)
        for change in ('missing', 'timing', 'duration'):
            broken = copy.deepcopy(original)
            if change == 'missing':
                broken['shots'].pop()
            elif change == 'timing':
                broken['shots'][1]['start'] = 6
            else:
                broken['shots'][0]['duration'] = 10
            with self.assertRaises(RuntimeError):
                validate_plan(broken)

    def test_shards_generate_every_scene_once_and_separate_thumbnail(self):
        def generate(prompt, target, seed):
            Image.new('RGB', (256, 256), 'navy').save(target)
        with tempfile.TemporaryDirectory() as temp, patch('image_cpu.generate', side_effect=generate) as worker:
            root = Path(temp)
            (root/'storyboard.json').write_text(json.dumps(plan()))
            records = []
            for shard in range(16):
                records.extend(generate_shard(root, SONG, shard).items())
            self.assertEqual(worker.call_count, 37)
            self.assertEqual(len(list(root.glob('scene-*.png'))), 36)
            self.assertTrue((root/'thumbnail-source.png').exists())
            self.assertEqual(len({spec['seed'] for _, spec in records}), 37)
            for shard in range(16):
                generate_shard(root, SONG, shard)
            self.assertEqual(worker.call_count, 37)
            changed = plan()
            changed['identity'] = 'new-song'
            (root/'storyboard.json').write_text(json.dumps(changed))
            generate_shard(root, SONG, 0)
            self.assertGreater(worker.call_count, 37)

    def test_safety_rejection_never_saves_image(self):
        worker = Mock(return_value=types.SimpleNamespace(nsfw_content_detected=[True], images=[Image.new('RGB', (256, 256))]))
        torch = types.SimpleNamespace(set_num_threads=Mock(), Generator=Mock())
        diffusers = types.SimpleNamespace(DiffusionPipeline=Mock(), DPMSolverMultistepScheduler=Mock())
        with tempfile.TemporaryDirectory() as temp, patch.object(image_cpu, '_pipeline', worker), patch.dict('sys.modules', {'torch': torch, 'diffusers': diffusers}):
            target = Path(temp)/'scene.png'
            with self.assertRaises(image_cpu.ImageSafetyBlocked):
                image_cpu.generate('Adult couple walking', target, seed=1)
            self.assertFalse(target.exists())

    def test_hindi_seo_metadata_has_no_internal_names_and_has_bounded_tags(self):
        song = optimize_metadata(copy.deepcopy(SONG), 'healing', '2026')
        self.assertIn('Hindi Album Song 2026', song['title'])
        self.assertIn('हिंदी एल्बम गीत', song['description'])
        self.assertLessEqual(len(song['title']), 100)
        self.assertEqual(song['description'].count('#'), 3)
        validate_song(song)
        for field in ('title', 'description', 'thumbnail_text'):
            with self.assertRaisesRegex(ValueError, 'Internal tool'):
                validate_song(dict(song, **{field: 'Generated using Qwen'}))
        with self.assertRaises(ValueError):
            validate_song(dict(song, lyrics='তোমার স্মৃতিতে আমার মন হারিয়ে যায়'))
        tags = metadata_tags(dict(song, tags=['a'*38+str(i) for i in range(30)]))
        self.assertLessEqual(sum(len(t)+(2 if ' ' in t else 0)+1 for t in tags), 480)

    def test_upload_language_is_hindi_and_description_is_public_copy_only(self):
        song = optimize_metadata(copy.deepcopy(SONG), 'healing', '2026')
        client = Mock()
        client.videos().insert().next_chunk.return_value = (None, {'id': 'video'})
        client.videos().list().execute.return_value = {'items': [{'snippet': {'channelId': 'channel'},
            'status': {'privacyStatus': 'public', 'uploadStatus': 'processed'}, 'contentDetails': {'definition': 'hd'}}]}
        with patch.dict('os.environ', {'EXPECTED_CHANNEL_ID': 'channel'}), patch('googleapiclient.http.MediaFileUpload'):
            publish(client, Path('.'), song, {'thumbnail_uploaded': True}, Mock())
        snippet = client.videos().insert.call_args.kwargs['body']['snippet']
        self.assertEqual(snippet['defaultLanguage'], 'hi')
        self.assertEqual(snippet['defaultAudioLanguage'], 'hi')
        self.assertEqual(snippet['description'], song['description'])
        self.assertNotIn('ACE-Step', snippet['description'])

    def test_timing_runtime_uses_pinned_multilingual_model_on_cpu(self):
        from lyric_video import transcribe, ASR_REPO, ASR_REVISION
        segments = [types.SimpleNamespace(words=[types.SimpleNamespace(**word) for word in TIMED])]
        model = Mock()
        model.transcribe.return_value = (iter(segments), None)
        whisper = Mock(return_value=model)
        with tempfile.TemporaryDirectory() as temp, patch('huggingface_hub.snapshot_download', return_value='/weights') as download, patch.dict('sys.modules', {'faster_whisper': types.SimpleNamespace(WhisperModel=whisper)}):
            root = Path(temp)
            words = transcribe(root, SONG, 'audio-hash', 180)
            self.assertEqual(len(words), len(TIMED))
            self.assertEqual(download.call_args.args[0], ASR_REPO)
            self.assertEqual(download.call_args.kwargs['revision'], ASR_REVISION)
            self.assertIs(download.call_args.kwargs['token'], False)
            self.assertEqual(whisper.call_args.kwargs['device'], 'cpu')
            self.assertEqual(model.transcribe.call_args.kwargs['language'], 'hi')
            self.assertTrue(model.transcribe.call_args.kwargs['word_timestamps'])
            transcribe(root, SONG, 'audio-hash', 180)
            model.transcribe.assert_called_once()

    def test_storyboard_batches_keep_real_timing_and_resume_completed_plan(self):
        from lyric_video import prepare_storyboard
        def request(endpoint, payload):
            schema = payload['response_format']['json_schema']['schema']
            ids = schema['properties']['scenes']['items']['properties']['index']['enum']
            scenes = [dict(index=index, prompt=f'Adult Indian couple beside the river, cinematic angle {index}, thoughtful expressions and soft blue light.') for index in ids]
            return {'choices': [{'message': {'content': json.dumps({'scenes': scenes})}}]}
        with tempfile.TemporaryDirectory() as temp, patch('pipeline.duration', return_value=180), patch('lyric_video.transcribe', return_value=TIMED), patch('lyrics_cpu.request_story', side_effect=request) as writer:
            root=Path(temp)
            (root/'song.wav').write_bytes(b'audio-fixture')
            result=prepare_storyboard(root, SONG)
            self.assertTrue(result['complete'])
            self.assertEqual(len(result['shots']),36)
            self.assertEqual(writer.call_count,6)
            self.assertEqual(result['shots'][1]['start'],5)
            prepare_storyboard(root, SONG)
            self.assertEqual(writer.call_count,6)

    def test_daily_rotation_preserves_varied_hindi_album_styles(self):
        start = dt.date(2026, 10, 26)
        profiles = [song_profile((start+dt.timedelta(days=i)).isoformat()) for i in range(8)]
        self.assertEqual(set(profiles), set(SONG_PROFILES))
        self.assertTrue(all('Hindi' in profile[1] for profile in profiles))


if __name__ == '__main__':
    unittest.main()
