import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from cartoon_story import CAST, VERSION, plan, validate_manifest, atomic, image_prompt
from cartoon_audio import prepare_audio, RATE, mix_scene
from cartoon_render import acting_plan


def fixture():
    scenes=[]
    for i in range(16):
        scenes.append(dict(index=i,speaker=['narrator','mira','theo','narrator'][i%4],
            text=f'At stop number {i} the two friends paused to examine the little wooden sign before deciding which path would lead them safely home together.',
            visual='Mira and Theo examine a wooden sign on a sunny woodland path, keeping their separate bodies clearly visible.',
            prompt='Family cartoon friends on a woodland path.', action='react',emotion='curious',sfx='none'))
    return dict(format=VERSION,language='en',cast=copy.deepcopy(CAST),title='The Upside Down Map',
        description='Two friends discover why their familiar path looks strange, then learn to check their assumptions together.',
        scenes=scenes,lyrics='\n'.join(s['text'] for s in scenes),prompt='map adventure',tags=['family cartoon'])


class StoryTests(unittest.TestCase):
    def test_story_planning_resumes_accepted_batches_and_preserves_cast(self):
        song=fixture();outline=dict(title=song['title'],summary=song['description'],setting='A sunny woodland with signposts and a small wooden bridge.',lesson='Checking assumptions together',beats=['Discover the next part of the woodland mystery.']*16)
        calls=[]
        def request(schema,prompt,seed):
            calls.append(prompt)
            if len(calls)==3: raise RuntimeError('interrupted worker')
            if len(calls)==1:return outline
            return dict(shots=[{k:s[k] for k in ('speaker','text','visual','action','emotion','sfx')} for s in song['scenes'][:4]])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch('cartoon_story.request',side_effect=request):
                with self.assertRaises(RuntimeError):plan(root,'test')
            saved=json.loads((root/'cartoon-draft.json').read_text())
            self.assertEqual(len(saved['batches']),1)
            remaining=[dict(shots=[{k:s[k] for k in ('speaker','text','visual','action','emotion','sfx')} for s in song['scenes'][i:i+4]]) for i in (4,8,12)]
            with patch('cartoon_story.request',side_effect=remaining) as model:
                completed=plan(root,'test')
                self.assertEqual(model.call_count,3)
            self.assertEqual(completed['cast'],CAST)
            self.assertNotIn('toddlers',completed['scenes'][0]['prompt'])
            with self.assertRaisesRegex(ValueError,'differs'):plan(root,'test','changed request')

    def test_only_grounded_actions_travel_without_dance_or_random_props(self):
        for action in ('react','wait'):
            p=acting_plan(dict(action=action,index=0))
            self.assertIsNone(p['intent']);self.assertIsNone(p['prop']);self.assertNotEqual(p['action'],'dance')
        for action in ('approach_friend','follow_friend','approach_ball'):
            p=acting_plan(dict(action=action,index=0));self.assertEqual(p['intent'],action)
            self.assertEqual(p['dance_variant'],'step')

    def test_english_manifest_cannot_accept_old_hindi_or_missing_cast(self):
        song=fixture();validate_manifest(song)
        for field,value in [('language','hi'),('cast',{}),('format','old-rhyme')]:
            bad=copy.deepcopy(song);bad[field]=value
            with self.assertRaises(ValueError):validate_manifest(bad)


class SpeechTests(unittest.TestCase):
    def test_voice_timing_and_recovery_do_not_duplicate_speech_inference(self):
        t=np.arange(RATE*8)/RATE;speech=(.08*np.sin(2*np.pi*220*t)).astype(np.float32)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);atomic(root/'song.json',fixture())
            voices=[]
            def synth(text,voice):voices.append(voice);return speech
            song=prepare_audio(root,synth)
            self.assertEqual(set(voices),{v['voice'] for v in CAST.values()})
            self.assertAlmostEqual(song['duration'],140.8)
            validate_manifest(song,timed=True)
            with patch('cartoon_audio.load_voice_engine',side_effect=AssertionError('cached audio regenerated')):
                prepare_audio(root)
            # A corrupted cached WAV must regenerate only that spoken shot.
            (root/'speech/shot-003.wav').write_bytes(b'corrupt')
            voices.clear();prepare_audio(root,synth);self.assertEqual(len(voices),1)
            from episode_packaging import public_metadata
            self.assertEqual(public_metadata(song)['title'],song['title'])
            from pipeline import validate_song,validate_media_duration
            validate_song(song);validate_media_duration(song,140.8)
            with self.assertRaises(ValueError):validate_media_duration(song,141.8)

    def test_short_or_silent_voice_never_commits_a_speech_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);atomic(root/'song.json',fixture())
            with self.assertRaises(ValueError):prepare_audio(root,lambda text,voice:np.zeros(RATE*8))
            self.assertFalse((root/'speech/shot-000.wav').exists())
            self.assertFalse((root/'song.wav').exists())

    def test_mix_keeps_speech_onsets_and_frame_boundaries_without_clipping(self):
        speech=np.ones(RATE*7,dtype=np.float32)*.1
        audio,frames=mix_scene(speech,dict(action='react',sfx='discovery'))
        self.assertEqual(len(audio),frames*960)
        self.assertGreater(audio[RATE].mean(),.08)
        self.assertLess(np.max(np.abs(audio)),.96)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg runtime required')
class RenderIntegrationTests(unittest.TestCase):
    def test_variable_spoken_timeline_assembles_without_losing_transition_time(self):
        import subprocess
        from cartoon_render import assemble, is_current
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);atomic(root/'song.json',fixture())
            t=np.arange(RATE*8)/RATE
            song=prepare_audio(root,lambda text,voice:(.08*np.sin(2*np.pi*220*t)).astype(np.float32))
            folder=root/'cartoon-motion';folder.mkdir()
            from PIL import Image
            for scene in song['scenes']:
                Image.new('RGB',(320,180),'green').save(root/f"scene-{scene['index']:03d}-source.png")
            Image.new('RGB',(320,180),'green').save(root/'thumbnail-source.png')
            native=folder/'sample.mp4'
            subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=blue:s=320x180:r=25',
                '-frames:v','220','-c:v','libx264','-pix_fmt','yuv420p',str(native)],check=True)
            for scene in song['scenes']:shutil.copyfile(native,folder/f"clip-{scene['index']:03d}.mp4")
            assemble(root,320,180)
            from pipeline import duration
            self.assertAlmostEqual(duration(root/'video.mp4'),140.8,delta=.1)
            self.assertTrue(is_current(root))
            subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(root/'video.mp4'),'-f','null','-'],check=True)
            (root/'song.wav').write_bytes(b'changed audio')
            self.assertFalse(is_current(root))

    def test_actor_render_uses_actual_shot_frames_and_reuses_verified_clip(self):
        from PIL import Image,ImageDraw
        from cartoon_render import render_shot,valid_clip
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);scene=fixture()['scenes'][0];scene.update(start=0,end=2.4)
            source=root/'scene-000-source.png';Image.new('RGB',(160,90),'green').save(source)
            folder=root/'characters/scene-000-source';folder.mkdir(parents=True)
            Image.new('RGBA',(160,90),'green').save(folder/'background.png')
            fg=Image.new('RGBA',(160,90));ImageDraw.Draw(fg).ellipse((40,20,70,80),fill='orange');fg.save(folder/'foreground.png')
            with patch('character_motion.prepare_layers'):
                target=render_shot(root,scene,320,180)
            valid_clip(target,60,320,180)
            with patch('character_motion.prepare_layers',side_effect=AssertionError('valid layers regenerated')):
                self.assertEqual(render_shot(root,scene,320,180),target)
