import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import unicodedata
from unittest.mock import Mock, MagicMock, patch

import hindi


class HindiLanguageTests(unittest.TestCase):
    def test_devanagari_words_and_matras_survive_normalization(self):
        self.assertEqual(hindi.normalized('  नन्हे दोस्त, फूलों में नाचें। '), 'नन्हे दोस्त फूलों में नाचें')
        self.assertNotEqual(hindi.normalized('कला'), hindi.normalized('काली'))
        self.assertEqual(hindi.normalized('ख़ुशी'), hindi.normalized(unicodedata.normalize('NFD','ख़ुशी')))

    def test_sung_grammar_accepts_hindi_and_rejects_english_transliteration_and_overload(self):
        import re
        for good in ['नन्हा खरगोश फूलों के पास कूदे', 'छम छम छम छम नाचो।']:
            self.assertIsNotNone(re.fullmatch(hindi.LYRIC_PATTERN, good))
        for bad in ['छम छम नाचो', 'Little bunny hops with friends', 'chham chham chham chham nacho',
                    ' '.join(['नन्हे'] * 13)]:
            self.assertIsNone(re.fullmatch(hindi.LYRIC_PATTERN, bad))

    def test_public_language_accepts_brand_but_rejects_other_scripts(self):
        hindi.require_hindi('प्यारे दोस्तों का नाच | Heart and Mind #Shorts')
        for text in ['Happy animal dance', 'नन्हे दोस्त dance करें', 'नन्हे दोस्त 朋友']:
            with self.assertRaises(ValueError): hindi.require_hindi(text)

    def test_model_language_failure_is_bounded_and_never_accepted(self):
        import rhyme_writer
        from lyrics_cpu import StoryGenerationError
        response = {'choices':[{'message':{'content':json.dumps({'verses':[{'lyric':'Little bunny hops with friends','visual':'Two toddlers and animals dance'}]})}}]}
        with patch('rhyme_writer.request_story', return_value=response) as model:
            with self.assertRaises(StoryGenerationError) as caught:
                rhyme_writer.request_json({'type':'object'}, 'Write one Hindi verse', 123)
        self.assertEqual(caught.exception.code, 'hindi_language')
        self.assertEqual(model.call_count, 3)
        self.assertIn('Hindi Devanagari', model.call_args.args[1]['messages'][-1]['content'])

    def test_hindi_model_response_keeps_visual_fields_english(self):
        import rhyme_writer
        value = {'verses':[{'lyric':'नन्हे दोस्त बगीचे में फूल चुनें', 'visual':'Two toddlers and a baby bunny gather flowers'}]}
        response = {'choices':[{'message':{'content':json.dumps(value,ensure_ascii=False)}}]}
        with patch('rhyme_writer.request_story', return_value=response):
            self.assertEqual(rhyme_writer.request_json({'type':'object'}, 'Hindi song', 123), value)

    def test_saved_hindi_outline_reaches_next_prompt_as_native_text(self):
        import rhyme_writer
        from test_rhyme_writer import fake_model
        from lyrics_cpu import StoryGenerationError
        prompts=[]
        def model(schema,prompt,seed,budget=2600):
            prompts.append(prompt)
            if 'chapters' not in schema['properties']:
                raise StoryGenerationError('Stop after inspecting the verse request')
            value=fake_model(schema,prompt,seed)
            value['title']='नन्हे दोस्तों की फूलों वाली सैर'
            value['description']='नन्हे दोस्त मिलकर फूलों के बगीचे में नाचते हैं।'
            return value
        with patch('rhyme_writer.request_json',side_effect=model), self.assertRaises(StoryGenerationError):
            rhyme_writer.write_rhyme('2026-11-09','unicode-prompt',240,[])
        self.assertIn('नन्हे दोस्तों की फूलों वाली सैर',prompts[-1])
        self.assertNotIn('\\u0928',prompts[-1])

    def test_hindi_actions_drive_reference_motion(self):
        self.assertIn('clap', hindi.motion_hint('मिलकर सब ताली बजाओ'))
        self.assertIn('jump', hindi.motion_hint('खुशी से कूदो उछलो'))
        self.assertIn('spin', hindi.motion_hint('गोल गोल घूमो'))


class HindiPipelineTests(unittest.TestCase):
    def song(self):
        import test_kids_rhymes
        fixture = test_kids_rhymes.KidsTests(); fixture.setUp()
        try: return fixture.song()
        finally: fixture.doCleanups()

    def test_new_song_uses_reference_form_and_hindi_validation(self):
        from pipeline import validate_song
        song = self.song()
        hindi.validate_song_language(song)
        self.assertEqual(song['duration'], 240)
        self.assertEqual(song['bpm'], 130)
        self.assertEqual([s['section'] for s in song['scenes'][:4]], ['chorus']*4)
        self.assertIn('clear Hindi diction', song['prompt'])
        bad = copy.deepcopy(song); bad['lyrics'] += '\nSing a happy song'
        with self.assertRaises(ValueError): validate_song(bad)

    def test_hindi_packaging_thumbnail_and_short_roundtrip(self):
        from test_episode_packaging import fixture_package
        from episode_packaging import validate_package, public_metadata, chapter_text
        from song_images import image_plan
        from shorts import short_metadata
        song = self.song(); song['packaging'] = fixture_package(song)
        validate_package(song['packaging'], song)
        for kind in ['video','shorts']:
            meta = public_metadata(song, kind)
            hindi.require_hindi(meta['title']); hindi.require_hindi(meta['description'])
        self.assertEqual(image_plan(song)[-1]['reference_scene'], 'scene-000')
        self.assertIn('अंतरा 1', chapter_text(song))
        meta = short_metadata(song,0,40)
        self.assertEqual(public_metadata(meta,'shorts'), song['packaging']['shorts'])

    def test_audio_model_receives_hindi_not_just_hindi_metadata(self):
        import music_cpu as music
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); native=root/'native.wav';native.write_bytes(b'fixture audio')
            torch=MagicMock(); params=Mock(); config=Mock()
            handler=Mock(device='cpu'); handler.initialize_service.return_value=(None,True)
            infer=Mock(return_value=Mock(success=True,audios=[{'path':str(native)}]))
            request=dict(_segment=True,prompt='Hindi nursery dance',lyrics='नन्हे दोस्त मिलकर गाएँ',duration=40,bpm=130)
            with patch.object(music,'checkpoints'),patch.object(music,'runtime',return_value=(torch,Mock(return_value=handler),params,config,infer)),patch.object(music,'reference_audio',return_value=None),patch('pipeline.duration',return_value=40):
                music.synthesize(request,root/'generated.wav',Path('/reviewed-source'),root/'models')
            self.assertEqual(params.call_args.kwargs['vocal_language'],'hi')
            self.assertEqual(params.call_args.kwargs['bpm'],130)

    def test_defaults_and_all_workflow_language_bindings_are_hindi(self):
        import yaml
        from upload_settings import load_settings
        with patch.dict(os.environ, {}, clear=True):
            settings=load_settings()
        self.assertEqual(settings['language'],'hi');self.assertEqual(settings['audio_language'],'hi')
        for path in Path('.github/workflows').glob('*.yml'):
            self.assertNotIn("inputs.video_language || 'en'",path.read_text())
            self.assertNotIn("inputs.audio_language || 'en'",path.read_text())
        jobs=yaml.safe_load(Path('.github/workflows/music.yml').read_text())['jobs']
        self.assertEqual(jobs['publish']['env']['VIDEO_LANGUAGE'], "${{ inputs.video_language || 'hi' }}")

    def test_destination_setup_and_channel_do_not_point_to_reference(self):
        self.assertIn("Asif-Rezan/Heart-and-Mind",Path('setup_accounts.py').read_text())
        for path in Path('.github/workflows').glob('*.yml'):
            self.assertNotIn('UCztvMrNCT34DO3DtzLPgWaw',path.read_text())
            self.assertNotIn('UCYjz7d66SsshimfpxZahlhQ',path.read_text())
        self.assertIn('heart_and_mind_hindi_kids_root',Path('storage.py').read_text())
        self.assertNotIn('297892583408910',Path('facebook_publish.py').read_text())
