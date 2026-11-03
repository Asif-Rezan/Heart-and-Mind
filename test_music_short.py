import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
import soundfile as sf
import yaml

from authored_song import load_authored_song
import music_cpu
import music_short as short
import music_video as mv
import pipeline
from story_media import digest
from story_image_review import VERSION, MODEL, REVISION


def reviewed_image(prompt,path,seed,contract,**kwargs):
    Image.new('RGB',(kwargs['width'],kwargs['height']),'teal').save(path)
    return dict(version=VERSION,model=MODEL,revision=REVISION,passed=True,source_sha256=digest(path),answers=[])


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.parent=load_authored_song('tum-laut-aao-2026-11-03')
        self.song=short.companion(self.parent,'parent')

    def test_companion_identity_supports_full_length_parent_ids(self):
        identity=short.short_id('a'*80)
        self.assertLessEqual(len(identity),80)
        self.assertTrue(identity.endswith('-short'))
        self.assertNotEqual(identity,short.short_id('a'*79+'b'))
        for invalid in ('../private','', 'a'*81):
            with self.assertRaises(ValueError):short.short_id(invalid)

    def test_separate_arrangement_uses_reviewed_hook_and_portrait_plans(self):
        self.assertEqual(self.song['duration'],45)
        self.assertNotEqual(self.song['prompt'],self.parent['prompt'])
        self.assertNotEqual(self.song['lyrics'],self.parent['lyrics'])
        self.assertNotIn('lyric_quality',self.song)
        self.assertEqual(len(mv.planned_timeline(self.song)['slots']),9)
        plan=mv.image_plan(self.song,{},0)
        self.assertEqual((plan['width'],plan['height']),(576,1024))
        self.assertIn('vertical portrait',plan['prompt'])
        self.assertIn('#Shorts',pipeline.upload_description(self.song))
        with self.assertRaises(ValueError):pipeline.validate_song(copy.deepcopy(self.song))
        pipeline.validate_song(copy.deepcopy(self.song),allow_short=True)

    def test_generates_portrait_images_without_any_audio_file(self):
        with tempfile.TemporaryDirectory() as folder,patch('music_video.generate_reviewed',side_effect=reviewed_image) as model:
            root=Path(folder)
            for shard in range(3):mv.generate_images(root,self.song,shard=shard,shards=3)
            self.assertEqual(model.call_count,9)
            self.assertFalse((root/'song.wav').exists())
            with Image.open(root/'music-scene-008-source.png') as image:self.assertEqual(image.size,(576,1024))
            with patch('pipeline.duration',return_value=45.2):
                (root/'song.wav').write_bytes(b'independent-audio')
                timing=mv.prepare_timeline(root,self.song,allow_short=True)
            # The extra fractional last slot reuses the last independently generated scene.
            self.assertEqual(mv.source_index(self.song,9),8)
            self.assertEqual(mv.image_plan(self.song,timing,8),mv.image_plan(self.song,{},8))

    def test_independent_short_worker_requests_45_seconds(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'native.wav';source.write_bytes(b'fresh-short')
            torch=Mock();torch.inference_mode.return_value.__enter__=Mock();torch.inference_mode.return_value.__exit__=Mock(return_value=False)
            handler=Mock(device='cpu');handler.initialize_service.return_value=('ok',True)
            params,config=Mock(),Mock()
            infer=Mock(return_value=types.SimpleNamespace(success=True,audios=[{'path':str(source)}]))
            with patch.object(music_cpu,'runtime',return_value=(torch,Mock(return_value=handler),params,config,infer)),patch.object(music_cpu,'checkpoints'),patch('pipeline.duration',return_value=45):
                music_cpu.synthesize(self.song,root/'song.wav',root/'source',root/'models')
            self.assertEqual(params.call_args.kwargs['duration'],45)
            self.assertEqual(params.call_args.kwargs['lyrics'],self.song['lyrics'])
            self.assertEqual((root/'song.wav').read_bytes(),b'fresh-short')
            for invalid in (0,29,60,180):
                with self.assertRaises(ValueError):music_cpu.validate_audio_duration(self.song,invalid)
            with self.assertRaises(ValueError):music_cpu.validate_audio_duration(self.parent,45)

    def test_short_upload_is_idempotent_and_uses_youtube_selected_frame(self):
        state={'video_id':'short-id'};client=Mock()
        client.videos.return_value.list.return_value.execute.return_value={'items':[{
            'snippet':{'channelId':'channel'},'status':{'uploadStatus':'processed','privacyStatus':'public'},'contentDetails':{'definition':'hd'}}]}
        with patch('pipeline.required',return_value='channel'):
            pipeline.publish(client,Path('/tmp/unused'),self.song,state,Mock())
        self.assertEqual(state['phase'],'published')
        self.assertEqual(state['thumbnail_mode'],'youtube-selected-frame')
        client.thumbnails.assert_not_called();client.videos.return_value.insert.assert_not_called()
        with self.assertRaisesRegex(RuntimeError,'Ambiguous upload'):
            pipeline.publish(client,Path('/tmp/unused'),self.song,{'upload_started':True},Mock())

    def test_cleanup_accepts_shorts_frame_mode_only_with_verified_public_metadata(self):
        import cleanup_drive
        state=dict(phase='published',video_id='short-id',song=self.song,thumbnail_mode='youtube-selected-frame')
        video=dict(id='short-id',snippet=dict(channelId='channel',title=self.song['title'],description=pipeline.upload_description(self.song),tags=pipeline.metadata_tags(self.song)),status=dict(privacyStatus='public',uploadStatus='processed'),processingDetails=dict(processingStatus='succeeded'),contentDetails=dict(definition='hd'))
        client=Mock();client.videos.return_value.list.return_value.execute.return_value={'items':[video]}
        with patch('cleanup_drive.required',return_value='channel'):
            cleanup_drive.verify_public(client,state)
            video['status']['privacyStatus']='private'
            with self.assertRaises(RuntimeError):cleanup_drive.verify_public(client,state)
        state.pop('thumbnail_mode')
        with self.assertRaises(RuntimeError):cleanup_drive.verify_public(client,state)

    def test_missing_prepared_companion_cannot_start_generation_during_publish(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'output/parent-short';root.mkdir(parents=True)
            (root/'song.json').write_text(json.dumps(self.song))
            with patch('music_short.Path',side_effect=lambda x:Path(folder)/x),patch('music_short.validate_media',side_effect=ValueError('missing prepared media')),patch('music_short.generate') as synth,patch('music_short.Store') as store:
                with self.assertRaisesRegex(ValueError,'missing prepared media'):short.publish_short('parent')
            synth.assert_not_called();store.assert_not_called()

    def test_short_cli_calls_the_dedicated_editor(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'output/parent-short';root.mkdir(parents=True)
            (root/'song.json').write_text(json.dumps(self.song))
            with patch('music_short.Path',side_effect=lambda x:Path(folder)/x),patch('sys.argv',['music_short.py','--parent-run','parent','--stage','render']),patch('music_short.render',autospec=True) as editor,patch('music_short.validate_media'):
                short.main()
            editor.assert_called_once_with(root,self.song,width=1080,height=1920)

    def test_short_cuts_follow_audio_energy_and_captions_have_honest_alignment(self):
        from short_edit import edit_plan
        samples=np.zeros(45*8000,dtype=np.float32)
        samples[11360:11520]=.8
        plan=edit_plan(self.song,45,samples)
        self.assertGreater(len(plan['slots']),9)
        self.assertAlmostEqual(plan['slots'][1]['start'],1.42,delta=.025)
        self.assertLessEqual(plan['slots'][0]['end'],1.5)
        self.assertEqual(plan['slots'][0]['start'],0)
        self.assertEqual(plan['slots'][-1]['end'],45)
        self.assertEqual(len({s['move'] for s in plan['slots']}),4)
        self.assertTrue(all(.8<=s['end']-s['start']<=3.2 for s in plan['slots']))
        self.assertEqual(plan['cards'][0]['start'],0)
        self.assertEqual(plan['alignment'],'editorial-lyric-cards-not-word-timestamps')
        self.assertTrue(all(a['end']==b['start'] for a,b in zip(plan['slots'],plan['slots'][1:])))

    def test_workflow_runs_both_music_engines_and_both_image_groups_independently(self):
        jobs=yaml.safe_load(Path('.github/workflows/music-hindi-songs.yml').read_text())['jobs']
        self.assertEqual(jobs['images']['needs'],['lyrics'])
        self.assertEqual(jobs['music']['needs'],'lyrics')
        self.assertEqual(jobs['shorts']['needs'],['lyrics'])
        self.assertEqual(len(jobs['images']['strategy']['matrix']['shard'])+4+2,20)
        self.assertNotIn('music-visual-input',str(jobs['images']))
        shortjobs=yaml.safe_load(Path('.github/workflows/music-short.yml').read_text())['jobs']
        self.assertEqual(shortjobs['music']['needs'],['plan'])
        self.assertEqual(shortjobs['images']['needs'],['plan'])
        self.assertEqual(len(shortjobs['images']['strategy']['matrix']['shard']),4)
        self.assertEqual(shortjobs['render']['needs'],['music','images'])
        installs=[x for x in shortjobs['images']['steps'] if 'pip install --no-cache-dir torch' in x.get('run','')]
        self.assertEqual(len(installs),1)
        self.assertIn('PUBLISH_ENABLED',shortjobs['publish']['if'])
        for name in ('music','images','render'):
            self.assertNotIn('YOUTUBE_TOKEN_JSON',str(shortjobs[name]['env']))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_real_portrait_edit_retains_independent_audio_and_measured_dimensions(self):
        with tempfile.TemporaryDirectory() as folder,patch('music_video.generate_reviewed',side_effect=reviewed_image):
            root=Path(folder);sr=24000
            # A brief fixture keeps the real portrait encoder smoke test fast.
            song=dict(self.song,duration=5)
            sf.write(root/'song.wav',.08*np.sin(2*np.pi*330*np.arange(sr*5)/sr),sr)
            mv.prepare_timeline(root,song,allow_short=True);mv.generate_images(root,song)
            from short_edit import render
            render(root,song,width=1080,height=1920,allow_test=True)
            info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height','-select_streams','v:0','-of','json',str(root/'video.mp4')],text=True))
            self.assertEqual(info['streams'][0],dict(width=1080,height=1920))
            self.assertAlmostEqual(pipeline.duration(root/'video.mp4'),5,delta=.1)
            self.assertEqual(json.loads((root/'music-render-state.json').read_text())['identity']['timing']['audio_sha256'],digest(root/'song.wav'))


if __name__=='__main__':unittest.main()
