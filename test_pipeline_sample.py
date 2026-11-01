"""The one-minute sample exercises production stages with an explicit small format."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
import yaml
from story_format import SAMPLE_FORMAT,FORMAT,duration_bounds,word_bounds,scenes_per_chapter
from story_writer import validate_story,save_json
from test_short_story import short_story
from test_story_parallel import outline_fixture


def sample_story():
    full=short_story();story=copy.deepcopy(full)
    story['format']=SAMPLE_FORMAT
    story['scenes']=story['scenes'][:12]
    story['scenes'][-1]['text']=full['scenes'][-1]['text']
    story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
    story['visuals']={str(i):full['visuals'][str(i)] for i in range(12)}
    story['thumbnail_scene']=5
    return story


class SampleContracts(unittest.TestCase):
    def test_sample_budget_does_not_relax_release_duration_or_scene_count(self):
        story=sample_story();validate_story(story)
        self.assertEqual(duration_bounds(story),(55,65))
        self.assertEqual(word_bounds(story),(120,165))
        self.assertEqual(scenes_per_chapter(story),2)
        story['format']=FORMAT
        self.assertEqual(duration_bounds(story),(240,360))
        with self.assertRaisesRegex(ValueError,'48-scene'):validate_story(story)

    def test_sample_cannot_reach_publication_even_via_direct_cli_function(self):
        from daily_story import publish_story
        with tempfile.TemporaryDirectory() as folder,patch('storage.Store') as store:
            with self.assertRaisesRegex(ValueError,'preview-only'):publish_story(Path(folder),sample_story(),'sample-test')
            store.assert_not_called()

    def test_real_planner_builds_six_two_scene_chapters_and_validates_assembly(self):
        from story_plan import prepare_outline,write_chapter,assemble_story
        reference=sample_story()
        def respond(schema,prompt,*args,**kwargs):
            props=schema['properties']
            if 'chapters' in props:return outline_fixture()
            if 'scene' in props:return dict(scene=5,thumbnail_prompt=reference['thumbnail_prompt'])
            if 'title' in props:return dict(title=reference['title'],description=reference['description'],tags=[f'Hindi story theme {i}' for i in range(8)])
            result={}
            checkpoint=Path(kwargs['checkpoint'])
            chapter=int(checkpoint.stem.rsplit('-',1)[-1]) if checkpoint.parent.name=='chapters' else None
            for key,spec in props.items():
                index=int(key.split('_')[-1])
                scene=reference['scenes'][(chapter*2+index) if chapter is not None else index]
                result[key]=dict(text=scene['text'],visual=scene['visual']) if spec['type']=='object' else reference['visuals'][str(index)]
            return result
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'STORY_FORMAT':SAMPLE_FORMAT}),patch('story_plan.ask',side_effect=respond),patch('story_packaging.ask',side_effect=respond),patch('story_engagement.ask',return_value=dict(hook=True,progression=True,payoff=True,cta=True,repairs=[])):
            root=Path(folder)
            prepare_outline(root,reference['run_id'],[])
            for i in range(6):write_chapter(root,reference['run_id'],i)
            story=assemble_story(root,reference['run_id'],[])
            validate_story(story)
            self.assertEqual(story['format'],SAMPLE_FORMAT)
            self.assertEqual(len(story['scenes']),12)
            self.assertEqual(story['lyrics'],reference['lyrics'])

    def test_workflow_uses_the_same_entrypoints_and_never_publishes_samples(self):
        workflow=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())
        jobs=workflow['jobs']
        scripts='\n'.join(step.get('run','') for job in jobs.values() for step in job.get('steps',[]))
        for stage in ('outline','chapter','assemble','voice','music-part','mix','images','render'):
            self.assertIn('--stage '+stage,scripts)
        upload=next(step for step in jobs['publish']['steps'] if '--stage publish ' in step.get('run',''))
        self.assertIn('!inputs.sample_mode',upload['if'])
        self.assertIn('!inputs.sample_mode',jobs['cleanup']['if'])
        self.assertFalse(Path('demo_background_story.py').exists())
        self.assertFalse(Path('.github/workflows/story-sample.yml').exists())


@unittest.skipUnless(shutil.which('ffmpeg') and importlib.util.find_spec('soundfile'),'FFmpeg + soundfile required')
class SamePipelineMedia(unittest.TestCase):
    def test_voice_score_mix_reference_images_and_join_share_release_code(self):
        import numpy as np
        import soundfile as sf
        from PIL import Image
        from story_voice import generate_voice
        from daily_story import generate_score_part,mix_score
        from story_video import generate_images,render
        from pipeline import duration
        story=sample_story()
        class Audio:
            def detach(self):return self
            def cpu(self):return self
            def numpy(self):return .1*np.sin(2*np.pi*220*np.arange(5*24000)/24000).astype(np.float32)
        def pipeline(text,**kwargs):yield text,None,Audio()
        def music(request,target,*args):
            self.assertEqual(request['duration'],30)
            sf.write(target,.06*np.sin(2*np.pi*110*np.arange(30*24000)/24000),24000)
        def image(prompt,path,**kwargs):Image.new('RGB',(64,36),'gold').save(path)
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'IMAGE_SHARD':'0','IMAGE_SHARDS':'1','STORY_VOICE_ENGINE':'kokoro','STORY_NARRATOR_VOICE':'hm_omega'}):
            root=Path(folder);save_json(root/'story.json',story)
            with patch.dict(sys.modules,{'torch':Mock()}),patch('story_voice.load_pipeline',return_value=(pipeline,'hm_omega')):
                timing=generate_voice(root,story)
            self.assertTrue(55<=timing['duration']<=65)
            with patch('story_music_cpu.generate_segment',side_effect=music):
                for i in range(3):generate_score_part(root,story,i)
            mix_score(root,story,timing)
            with patch('story_image_cpu.generate',side_effect=image):generate_images(root,story)
            render(root,story,timing,width=128,height=72)
            self.assertAlmostEqual(duration(root/'video.mp4'),timing['duration'],places=1)
            self.assertAlmostEqual(duration(root/'song.wav'),timing['duration'],delta=.05)
            self.assertTrue((root/'thumbnail.jpg').is_file())
            self.assertTrue((root/'render-state.json').is_file())
