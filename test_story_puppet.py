"""Both renderers, deterministic daily rotation, resumability and moving rigs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from PIL import ImageChops
from story_puppet import Stage, scene_plan, encode
from story_video import generate_images, backend, video_style
from story_writer import save_json
from test_short_story import short_story,timeline


class RendererSelection(unittest.TestCase):
    def test_daily_rotation_alternates_and_crosses_month_and_year(self):
        from datetime import date,timedelta
        with patch.dict(os.environ,{'STORY_VIDEO_STYLE':'auto'}):
            for start in (date(2026,11,1),date(2026,11,30),date(2026,12,31)):
                styles=[video_style(Path('/unused')/f'story-{start+timedelta(days=i)}') for i in range(3)]
                self.assertNotEqual(styles[0],styles[1])
                self.assertEqual(styles[0],styles[2])
            self.assertEqual(video_style('/unused/story-2026-11-01'),'puppet')
            self.assertEqual(video_style('/unused/story-2026-11-02'),'background')

    def test_saved_style_wins_over_date_and_conflicting_explicit_style_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            save_json(Path(folder)/'video-style.json',dict(style='background'))
            with patch.dict(os.environ,{'STORY_VIDEO_STYLE':'auto'}):
                self.assertEqual(video_style(folder),'background')
            with patch.dict(os.environ,{'STORY_VIDEO_STYLE':'puppet'}),self.assertRaisesRegex(ValueError,'saved run'):
                video_style(folder)
            with patch.dict(os.environ,{'STORY_VIDEO_STYLE':'typo'}),self.assertRaises(ValueError):video_style(folder)

    def test_old_prepared_image_runs_remain_background_without_style_marker(self):
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'STORY_VIDEO_STYLE':'auto'}):
            save_json(Path(folder)/'image-manifest-00.json',{'0':dict(model='segmind/SSD-1B')})
            self.assertEqual(video_style(folder),'background')

    def test_workflow_resolves_and_persists_the_date_choice_after_artifact_restore(self):
        import yaml
        import sys
        workflow=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())
        steps=workflow['jobs']['outline']['steps']
        identity=next(step for step in steps if step.get('id')=='identity')
        with tempfile.TemporaryDirectory() as folder:
            # Execute the actual workflow identity script with a saved custom run.
            root=Path(folder)
            shutil.copyfile('story_video_style.py',root/'story_video_style.py')
            save_json(root/'output'/'custom-run'/'video-style.json',dict(style='background'))
            output=root/'outputs.txt'
            env=dict(os.environ,STORY_VIDEO_STYLE='auto',REQUESTED_RUN_ID='custom-run',GITHUB_OUTPUT=str(output),PATH=str(Path(sys.executable).parent)+os.pathsep+os.environ['PATH'])
            subprocess.run(['bash','-e','-c',identity['run']],cwd=root,env=env,check=True)
            self.assertIn('video_style=background',output.read_text())
            self.assertIn('run_id=custom-run',output.read_text())
        images=workflow['jobs']['images']
        self.assertEqual(images['env']['STORY_VIDEO_STYLE'],'${{ needs.plan.outputs.video_style }}')
        runtime=next(step for step in images['steps'] if 'requirements-images-cpu.txt' in step.get('run',''))
        self.assertEqual(runtime['if'],"env.STORY_VIDEO_STYLE == 'background'")

    def test_background_path_still_generates_original_reference_images(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'STORY_VIDEO_STYLE':'background','IMAGE_SHARD':'0','IMAGE_SHARDS':'18'}):
            root=Path(folder);save_json(root/'timing.json',timeline())
            def draw(prompt,path,**kwargs):Image.new('RGB',(64,36),'gold').save(path)
            with patch('story_image_cpu.generate',side_effect=draw) as model:
                generate_images(root,short_story())
                self.assertEqual(model.call_count,7)
                self.assertTrue((root/'cast-reference-00.png').exists())
                self.assertEqual(backend(root).__name__,'story_background_video')
                generate_images(root,short_story())
                self.assertEqual(model.call_count,7)


class PuppetAnimation(unittest.TestCase):
    def test_cast_is_consistent_while_action_setting_prop_and_emotion_follow_story(self):
        story=short_story()
        story['visuals']['0']='Ram walks sadly in a garden carrying a letter.'
        story['visuals']['1']='Ram writes in a school classroom with a book, happy smile.'
        story['scenes'][0]['text']='';story['scenes'][1]['text']=''
        a=scene_plan(story,dict(index=0));b=scene_plan(story,dict(index=1))
        self.assertEqual(a['cast'],b['cast'])
        self.assertEqual((a['setting'],a['action'],a['prop']),('garden','walk','letter'))
        self.assertEqual((b['setting'],b['action'],b['prop'],b['emotion']),('school','write','book','happy'))
        stage=Stage(a,640,360)
        f1=stage.frame(.2);f2=stage.frame(.8)
        self.assertIsNotNone(ImageChops.difference(f1,f2).getbbox())
        # Static environment stays fixed while the articulated rig moves.
        self.assertIsNone(ImageChops.difference(f1.crop((0,0,100,100)),f2.crop((0,0,100,100))).getbbox())

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
    def test_real_encoded_frames_move_and_match_duration(self):
        from pipeline import duration
        story=short_story();plan=scene_plan(story,dict(index=0))
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'motion.mp4'
            encode(plan,target,25,25,320,180)
            self.assertAlmostEqual(duration(target),1,places=2)
            frames=[]
            for at in ('0.2','0.8'):
                result=subprocess.run(['ffmpeg','-v','error','-ss',at,'-i',str(target),'-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'],capture_output=True,check=True)
                frames.append(result.stdout)
            self.assertNotEqual(frames[0],frames[1])
            self.assertEqual(len(frames[0]),320*180*3)
