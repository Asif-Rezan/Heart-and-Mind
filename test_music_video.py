import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw
import soundfile as sf

import music_video as mv
from story_image_review import VERSION as REVIEW_VERSION, MODEL, REVISION
from story_media import digest


SONG=dict(title='तेरे साथ',lyrics='[Verse 1]\nतेरे साथ चलना है\nनई सुबह फिर आएगी\n[Chorus]\nदिल में उम्मीद रखनी है',
          prompt='Solo male Hindi acoustic pop, 80 BPM',duration=195,visual_mood='romance',video_format=mv.FORMAT,
          background_prompt='An adult couple share an umbrella beside a quiet riverside tea stall in the rain',
          thumbnail_prompt='An adult couple exchange a folded letter beneath a warm lamp, with tender hopeful expressions')


def fixture(root,seconds=12.32):
    (root/'song.json').write_text(json.dumps(SONG,ensure_ascii=False))
    sr=24000;t=np.arange(round(seconds*sr))/sr
    sf.write(root/'song.wav',.08*np.sin(2*np.pi*220*t),sr)
    timing=mv.prepare_timeline(root,SONG,allow_short=True)
    for slot in timing['slots']:
        color=('#bd3434','#3265bb','#32aa65')[slot['index']%3]
        image=Image.new('RGB',(640,360),color)
        ImageDraw.Draw(image).rectangle((60,60,160,180),fill='white')
        image.save(root/f"music-scene-{slot['index']:03d}-source.png")
    Image.new('RGB',(1344,768),'teal').save(root/'thumbnail-source.png')
    return timing


class MusicVideoTests(unittest.TestCase):
    def test_singing_engine_is_the_exact_saved_music_implementation(self):
        self.assertEqual(Path('music_cpu.py').read_bytes(),Path('legacy/hindi-music/music_cpu.py').read_bytes())

    def test_prepared_publication_cannot_start_music_when_assets_are_missing(self):
        import pipeline
        from unittest.mock import Mock
        store=Mock();store.load.side_effect=[{},[]]
        song=dict(SONG,description='An original Hindi song.')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'output'/'new-song';root.mkdir(parents=True)
            (root/'song.json').write_text(json.dumps(song))
            with patch('pipeline.Path',side_effect=lambda value:Path(folder)/value),patch('pipeline.Store',return_value=store),patch('pipeline.youtube_client'),patch('music_cpu.generate') as synth:
                with self.assertRaisesRegex(RuntimeError,'assets missing'):
                    pipeline.run('new-song',require_prepared=True)
                synth.assert_not_called();store.upload.assert_not_called()

    def test_music_stage_keeps_saved_audio_and_builds_visual_timing(self):
        import prepare_music
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'output'/'saved-song';root.mkdir(parents=True)
            (root/'song.json').write_text(json.dumps(dict(SONG,description='Original music.')))
            (root/'song.wav').write_bytes(b'saved-audio')
            with patch('prepare_music.Path',side_effect=lambda value:Path(folder)/value),patch('prepare_music.duration',return_value=195),patch('prepare_music.generate') as synth,patch('music_video.prepare_timeline') as timing:
                prepare_music.prepare('saved-song','music',motion_video=True)
                synth.assert_not_called();timing.assert_called_once()
            self.assertEqual((root/'song.wav').read_bytes(),b'saved-audio')
            self.assertEqual(json.loads((root/'song.json').read_text())['video_format'],mv.FORMAT)

    def test_five_second_slots_follow_actual_fractional_audio_length(self):
        slots=mv.visual_timeline(195.24)
        self.assertEqual(len(slots),40)
        self.assertEqual([s['start'] for s in slots[:4]],[0,5,10,15])
        self.assertEqual(slots[-1]['end'],195.24)
        self.assertAlmostEqual(sum(s['end']-s['start'] for s in slots),195.24)
        self.assertEqual(mv.visual_timeline(195)[-1]['start'],190)
        for value in (0,float('nan'),float('inf'),361):
            with self.assertRaises(ValueError):mv.visual_timeline(value)

    def test_uses_current_image_backend_style_and_native_full_hd_thumbnail(self):
        timing=dict(slots=mv.visual_timeline(195))
        plans=[mv.image_plan(SONG,timing,i) for i in range(39)]
        self.assertEqual(len({p['seed'] for p in plans}),39)
        self.assertTrue(all(p['art_version']==mv.ART_VERSION and p['steps']==20 for p in plans))
        self.assertTrue(all(p['model']==mv.MODEL and p['revision']==mv.REVISION for p in plans))
        self.assertTrue(all('woman, 28' in p['contract']['people'] and 'man, 30' in p['contract']['people'] for p in plans))
        thumb=mv.image_plan(SONG,timing,0,'thumbnail')
        self.assertEqual((thumb['width'],thumb['height']),(1344,768))
        self.assertIn('folded letter',thumb['contract']['event'])
        self.assertEqual(thumb['contract']['checks'][1]['answers'],['two'])
        self.assertNotIn('school',thumb['contract']['event'])
        healing=mv.image_plan(dict(SONG,visual_mood='healing'),timing,0)
        self.assertNotIn('; man',healing['contract']['people'])
        self.assertNotIn('man',healing['contract']['checks'][0]['answers'])

    def test_music_face_direction_survives_retries_and_short_token_budget(self):
        from story_art_style import focused_prompt
        timing=dict(slots=mv.visual_timeline(10))
        for kind in ('background','thumbnail'):
            plan=mv.image_plan(SONG,timing,0,kind)
            for attempt in (0,1):
                prompt=focused_prompt(plan['contract'],kind,attempt,
                                      token_count=lambda text:len(text.split())+30)
                self.assertIn('A man and a woman embracing',prompt)
                self.assertNotIn('An adult couple',prompt)
                self.assertNotIn('warm',prompt)
                self.assertIn('both faces visible',prompt.lower())
                self.assertIn('Neutral white balance',prompt)
                self.assertIn('Natural colors',prompt)
                self.assertNotIn('Cool blue',prompt)
                self.assertNotIn('Wide shot',prompt)
            self.assertIn(dict(question='How many faces are visible?',answers=['two']),
                          plan['contract']['checks'])

    def test_failed_music_review_cannot_publish_best_candidate(self):
        from story_image_review import generate_reviewed
        contract=mv.scene_contract(SONG,0,1)
        def draw(prompt,path,**kwargs):
            Image.new('RGB',(256,256),'navy').save(path)
        with tempfile.TemporaryDirectory() as folder, \
                patch('story_image_cpu.generate',side_effect=draw), \
                patch('story_image_review.review_image',return_value=dict(passed=False,answers=[])):
            target=Path(folder)/'scene.png'
            with self.assertRaisesRegex(RuntimeError,'couple/face review failed'):
                generate_reviewed('unused',target,1,contract)
            self.assertFalse(target.exists())

    def test_image_resume_and_packaging_keep_only_the_owner_files(self):
        def draw(prompt,path,seed,contract,**kwargs):
            Image.new('RGB',(kwargs['width'],kwargs['height']),'navy').save(path)
            return dict(version=REVIEW_VERSION,model=MODEL,revision=REVISION,passed=True,source_sha256=digest(path),answers=[])
        with tempfile.TemporaryDirectory() as folder,patch('music_video.generate_reviewed',side_effect=draw) as model:
            root=Path(folder)/'song-run';root.mkdir();fixture(root)
            mv.generate_images(root,SONG,shard=0,shards=2)
            self.assertEqual(model.call_count,3)  # Slots 0, 2 and the separate thumbnail.
            mv.generate_images(root,SONG,shard=0,shards=2)
            self.assertEqual(model.call_count,3)
            destination=Path(folder)/'owned'
            mv.package_images(root,destination,0,2)
            names={p.name for p in (destination/root.name).iterdir()}
            self.assertIn('music-scene-000-source.png',names)
            self.assertIn('music-scene-002-source.png',names)
            self.assertNotIn('music-scene-001-source.png',names)
            self.assertIn('thumbnail.jpg',names)
            with Image.open(destination/root.name/'thumbnail.jpg') as image:self.assertEqual(image.size,(1920,1080))

    def test_only_music_owns_the_daily_schedule_and_publish_cannot_generate(self):
        import yaml
        music=yaml.safe_load(Path('.github/workflows/music-hindi-songs.yml').read_text())
        story=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())
        self.assertTrue(set(music).issubset({'name','on','env','permissions','concurrency','jobs','run-name'}))
        self.assertEqual(music['on']['schedule'][0]['cron'],'0 21 * * *')
        self.assertNotIn('schedule',story['on'])
        self.assertEqual(music['jobs']['images']['needs'],['lyrics','music'])
        self.assertEqual(len(music['jobs']['images']['strategy']['matrix']['shard']),12)
        publish=music['jobs']['publish']['steps']
        commands=' '.join(step.get('run','') for step in publish)
        self.assertIn('--require-prepared',commands)
        self.assertNotIn('--stage music',commands)
        self.assertNotIn('EXPECTED_CHANNEL_ID',str(music['jobs']['images']['env']))

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_real_edit_keeps_audio_duration_and_dissolves_at_five_second_boundaries(self):
        from pipeline import duration
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);fixture(root)
            mv.render(root,SONG,width=320,height=180,allow_short=True)
            self.assertAlmostEqual(duration(root/'video.mp4'),12.32,delta=.08)
            def color(time):
                data=subprocess.check_output(['ffmpeg','-v','error','-ss',str(time),'-i',str(root/'video.mp4'),
                    '-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
                return np.frombuffer(data,dtype=np.uint8).reshape(180,320,3)[35:55,170:190].mean(axis=(0,1))
            red=color(4.8);mixed=color(5.2);blue=color(5.7);green=color(10.7)
            self.assertGreater(red[0],red[2]*1.8)
            self.assertGreater(blue[2],blue[0]*1.8)
            self.assertGreater(green[1],green[0]*1.5)
            self.assertGreater(mixed[0],blue[0]);self.assertGreater(mixed[2],red[2])
            old=digest(root/'video.mp4')
            with patch('music_video.run_ffmpeg',side_effect=AssertionError('Cached edit should be reused')):
                mv.render(root,SONG,width=320,height=180,allow_short=True)
            self.assertEqual(digest(root/'video.mp4'),old)
            # A changed source invalidates the render and source-owned clip cache.
            Image.new('RGB',(640,360),'yellow').save(root/'music-scene-000-source.png')
            mv.render(root,SONG,width=320,height=180,allow_short=True)
            self.assertNotEqual(digest(root/'video.mp4'),old)


if __name__=='__main__':unittest.main()
