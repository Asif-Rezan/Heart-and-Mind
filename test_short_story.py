"""New release contract: speech fidelity, 4s scene alignment, shared cast and honest thumbnail."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from story_format import FORMAT
from story_writer import repeated_scenes, validate_story, save_json
from story_video import visual_timeline, thumbnail_slot, generate_images
from story_voice import synthesize_chunks, voice_identity
from test_daily_story import example_story


def short_story():
    story=example_story()
    story['format']=FORMAT
    import random
    words=['दुकान','घर','सड़क','खेत','किताब','पेड़','नदी','गाँव','माँ','पिता','मेहनत','चिट्ठी','काम','दिन','सुबह','उम्मीद','सपना','हिम्मत','रास्ता','विश्वास','बच्चा','दोस्त']
    for i,scene in enumerate(story['scenes']):
        scene.update(speaker='narrator',text=' '.join(random.Random(i).sample(words,13))+'।')
    story['scenes'][-1]['text']='इस फैसले पर आपकी क्या राय है, टिप्पणी में अपनी बात हमें बताइए।'
    story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
    story['visuals']={str(i):f'Ram, blue kurta, black hair, opens parcel {i} in his village shop, warm 3D storybook.' for i in range(48)}
    story['thumbnail_scene']=30
    story['thumbnail_prompt']='Ram with black hair in a blue kurta holds the story letter in his village shop, large thoughtful face, bright warm face lighting, cool blue background, uncluttered composition.'
    return story


def timeline(seconds=300):
    return dict(duration=seconds,speed=.95,scenes=[dict(index=i,start=i*seconds/48,end=(i+1)*seconds/48) for i in range(48)])


class ShortStoryContract(unittest.TestCase):
    def test_single_voice_and_word_budget(self):
        story=short_story()
        validate_story(story)
        story['scenes'][2]['speaker']='female'
        with self.assertRaisesRegex(ValueError,'one narrator'):
            validate_story(story)

    def test_exact_sentence_echo_across_and_within_scenes_is_rejected(self):
        story=short_story()
        story['scenes'][3]['text']=story['scenes'][2]['text']
        self.assertIn(3,repeated_scenes(story['scenes']))
        with self.assertRaisesRegex(ValueError,'repeated_story_lines'):
            validate_story(story)
        line='उसने खिड़की के पास बैठकर अपनी माँ को पहली चिट्ठी लिखी।'
        self.assertEqual(repeated_scenes([dict(text=line+' '+line)]),[0])

    def test_every_visual_interval_is_four_seconds_and_matches_dominant_spoken_beat(self):
        story=short_story()
        for seconds in (240,300,359.72,360):
            timing=timeline(seconds)
            slots=visual_timeline(story,timing)
            self.assertEqual(slots[0]['start'],0)
            self.assertEqual(slots[-1]['end'],seconds)
            self.assertTrue(all(s['end']-s['start']==4 for s in slots[:-1]))
            self.assertLessEqual(slots[-1]['end']-slots[-1]['start'],4)
            for slot in slots:
                chosen=timing['scenes'][slot['story_scene']]
                overlap=lambda s:max(0,min(slot['end'],s['end'])-max(slot['start'],s['start']))
                self.assertEqual(overlap(chosen),max(map(overlap,timing['scenes'])))
        for seconds in (239,361,600):
            with self.assertRaises(ValueError):
                visual_timeline(story,timeline(seconds))

    def test_thumbnail_is_actual_central_story_frame(self):
        story=short_story(); timing=timeline()
        index=thumbnail_slot(story,timing)
        self.assertEqual(visual_timeline(story,timing)[index]['story_scene'],30)
        self.assertNotEqual(index,0)

    def test_puppets_share_cast_and_follow_timeline_and_cache(self):
        story=short_story()
        with tempfile.TemporaryDirectory() as folder,patch('story_image_cpu.generate') as model:
            root=Path(folder);save_json(root/'timing.json',timeline())
            with patch.dict(os.environ,{'IMAGE_SHARD':'0','IMAGE_SHARDS':'18'}):
                generate_images(root,story)
                manifest=json.loads((root/'image-manifest-00.json').read_text())
                self.assertIn(story['visuals']['0'],manifest['0']['visual'])
                self.assertEqual(manifest['18']['start'],72)
                self.assertEqual(manifest['18']['story_scene'],11)
                self.assertEqual(manifest['0']['cast'],manifest['18']['cast'])
                thumb=json.loads((root/'thumbnail-manifest.json').read_text())
                self.assertEqual(thumb['story_scene'],30)
                before=(root/'scene-000-source.png').stat().st_mtime_ns
                generate_images(root,story)
                self.assertEqual(before,(root/'scene-000-source.png').stat().st_mtime_ns)
                story['visuals']['0']='Ram in his blue kurta folds a letter inside his village shop.'
                generate_images(root,story)
                self.assertEqual(json.loads((root/'scene-000-puppet.json').read_text())['prop'],'letter')
                self.assertNotEqual(before,(root/'scene-000-source.png').stat().st_mtime_ns)
                model.assert_not_called()

    def test_voice_rejects_pipeline_text_echo_before_saving_audio(self):
        text='उसने खिड़की के पास बैठकर अपनी माँ को पहली चिट्ठी लिखी।'
        class Audio:
            def detach(self): return self
            def cpu(self): return self
            def numpy(self): return [1,2]
        def repeated(*args,**kwargs):
            yield text,None,Audio()
            yield text,None,Audio()
        with self.assertRaisesRegex(RuntimeError,'coverage mismatch'):
            synthesize_chunks(repeated,text,'hm_omega',.95)
        calls=[]
        def valid(source,**kwargs):
            calls.append(kwargs)
            yield source,None,Audio()
        self.assertEqual(synthesize_chunks(valid,text,'hm_omega',.95),[[1,2]])
        self.assertIsNone(calls[0]['split_pattern'])
        self.assertNotEqual(voice_identity(short_story(),.95),voice_identity(example_story(),.95))


class ShortStoryPlanning(unittest.TestCase):
    def test_visual_plan_uses_final_narration_and_resumes_without_model_calls(self):
        from story_plan import prepare_visuals
        story=short_story();story.pop('visuals');story.pop('thumbnail_scene');story.pop('thumbnail_prompt')
        prompts=[]
        def ask(schema,prompt,*args,**kwargs):
            prompts.append(prompt)
            if 'scene' in schema['properties']:
                return dict(scene=31,thumbnail_prompt='Ram, blue kurta and black hair, holds the story parcel in the village shop, large expressive face, bright contrasting warm and cool colors, clean mobile composition.')
            return {key:f'Ram, black hair and blue kurta, opens the exact story parcel in scene {key} inside the village shop.' for key in schema['properties']}
        with tempfile.TemporaryDirectory() as folder,patch('story_plan.ask',side_effect=ask) as model:
            prepare_visuals(Path(folder),story)
            self.assertEqual(model.call_count,7)
            self.assertEqual(story['thumbnail_scene'],31)
            self.assertIn(story['scenes'][0]['text'],prompts[0])
            self.assertIn(story['characters'],prompts[0])
            fresh=short_story();fresh.pop('visuals');fresh.pop('thumbnail_scene');fresh.pop('thumbnail_prompt')
            prepare_visuals(Path(folder),fresh)
            self.assertEqual(model.call_count,7)
            self.assertEqual(fresh['visuals'],story['visuals'])

    def test_unfixed_repetitions_fail_before_narration(self):
        from story_plan import repair_repetition
        story=short_story();story['scenes'][1]['text']=story['scenes'][0]['text']
        def echo(schema,*args,**kwargs):
            return {key:dict(text=story['scenes'][0]['text'],visual=story['scenes'][0]['visual']) for key in schema['properties']}
        with tempfile.TemporaryDirectory() as folder,patch('story_plan.ask',side_effect=echo),self.assertRaisesRegex(ValueError,'repeated_story_lines'):
            repair_repetition(Path(folder),story)


import shutil
@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class ShortMediaSmoke(unittest.TestCase):
    def test_real_four_minute_render_cuts_on_four_seconds_and_uses_story_thumbnail(self):
        import subprocess
        from story_video import render,render_clips
        from pipeline import duration
        from story_media import digest
        story=short_story();timing=timeline(240)
        for i,scene in enumerate(timing['scenes']):
            scene['start']=i*4 if i<47 else 188
            scene['end']=(i+1)*4 if i<47 else 240
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            save_json(root/'story.json',story);save_json(root/'timing.json',timing)
            slots=visual_timeline(story,timing)
            for scene in story['scenes']:scene['text']=''
            for i in range(48):
                story['visuals'][str(i)]=('Ram walks in a sunny garden.' if i%2==0 else 'Ram writes a letter in a home kitchen.')
            generate_images(root,story)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=200:sample_rate=24000:duration=240',str(root/'song.wav')],check=True)
            for shard in range(3):
                render_clips(root,story,timing,width=128,height=72,shard=shard,shards=3)
            render(root,story,timing,width=128,height=72,prepared_clips=True)
            self.assertAlmostEqual(duration(root/'video.mp4'),240,places=1)
            samples=[]
            for at in (3.8,4.2,8.2):
                target=root/f'frame-{at}.png'
                subprocess.run(['ffmpeg','-v','error','-y','-ss',str(at),'-i',str(root/'video.mp4'),'-frames:v','1',str(target)],check=True)
                with Image.open(target) as frame:samples.append(frame.getpixel((5,45)))
            self.assertNotEqual(samples[0],samples[1])
            self.assertEqual(samples[0],samples[2])
            with Image.open(root/'thumbnail.jpg') as thumb, Image.open(root/'thumbnail-source.png') as source:
                from PIL import ImageOps,ImageChops,ImageStat
                difference=ImageChops.difference(thumb.convert('RGB'),ImageOps.fit(source.convert('RGB'),(1280,720)))
                self.assertLess(max(ImageStat.Stat(difference).mean),4)


def setUpModule():
    global _puppet_style_patch
    _puppet_style_patch=patch.dict(os.environ,{'STORY_VIDEO_STYLE':'puppet'})
    _puppet_style_patch.start()


def tearDownModule():
    _puppet_style_patch.stop()
