"""Regression coverage for failed outline lengths and independent production workers."""
import contextlib
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator, ValidationError
import yaml

from story_writer import OUTLINE, CHAPTER, ask, planning_schema, normalize_planning, save_json, text_hash
from story_plan import prepare_outline, write_chapter, assemble_story, StoryValidationError
from test_daily_story import example_story


def outline_fixture():
    return dict(title='एक नई शुरुआत',description='यह एक साधारण दुकानदार के साहस और समझ की मौलिक प्रेरणादायक कहानी है।',
        summary=('An Indian shopkeeper struggles with falling sales and learns to listen to his neighbours. '
                 'He changes his service through patient work and earns their trust.'),
        characters='Ram, Indian shopkeeper, short black hair, blue kurta. Sita, his wife, green sari and tied black hair.',
        world='A beautiful pastel Indian village market, warm cinematic morning light.',
        chapters=[f'Chapter {i+1}: Ram takes a different concrete step in his village shop, keeping his family informed.' for i in range(6)])


def chapter_fixture():
    scenes=copy.deepcopy(example_story()['scenes'][:8])
    for scene in scenes:
        scene.pop('index')
    return dict(scenes=scenes)


def slot_response(schema):
    scene=chapter_fixture()['scenes'][0]
    return {key:dict(text=scene['text'],visual=scene['visual']) for key in schema['properties']}


class PlanningLengthRegression(unittest.TestCase):
    def test_long_summary_and_all_planning_fields_normalize_before_strict_validation(self):
        raw=outline_fixture()
        raw['summary']='A complete planning sentence about listening carefully and making an honest choice. '*30
        raw['title']='एक नई शुरुआत और एक बेहतर जीवन की कहानी '*10
        raw['description']='यह एक मौलिक कहानी है। '*120
        raw['characters']='Ram wears a blue kurta and Sita wears a green sari. '*30
        raw['world']='The village has a beautiful green market and warm light. '*20
        raw['chapters']=['A detailed chapter beat about a concrete action and its consequence. '*20]*6
        with self.assertRaises(ValidationError):
            Draft202012Validator(OUTLINE).validate(raw)
        def inference(endpoint,payload):
            # Reproduce the actual inference validator that previously failed
            # three times before story code could receive the long summary.
            Draft202012Validator(payload['response_format']['json_schema']['schema']).validate(raw)
            return {'choices':[{'message':{'content':json.dumps(raw)}}]}
        with tempfile.TemporaryDirectory() as temporary,patch('lyrics_cpu.request_story',side_effect=inference) as model:
            checkpoint=Path(temporary)/'outline-response.json'
            result=ask(OUTLINE,'Original story',123,checkpoint=checkpoint)
            Draft202012Validator(OUTLINE).validate(result)
            self.assertLessEqual(len(result['summary']),700)
            self.assertEqual(json.loads(checkpoint.read_text()),raw)
            model.assert_called_once()

    def test_visual_bounds_never_modify_spoken_hindi(self):
        raw=chapter_fixture()
        text=raw['scenes'][0]['text']
        raw['scenes'][0]['visual']='A shopkeeper opens his village shop in soft beautiful lighting. '*20
        Draft202012Validator(planning_schema(CHAPTER)).validate(raw)
        result=normalize_planning(raw,CHAPTER)
        self.assertEqual(result['scenes'][0]['text'],text)
        self.assertLessEqual(len(result['scenes'][0]['visual']),360)
        self.assertEqual(planning_schema(CHAPTER)['properties']['scenes']['items']['properties']['text']['maxLength'],400)
        raw['scenes'][0]['text']='शब्द '*101
        with self.assertRaises(ValidationError):
            Draft202012Validator(planning_schema(CHAPTER)).validate(raw)

    def test_missing_fields_and_wrong_chapter_count_are_not_silently_repaired(self):
        raw=outline_fixture()
        raw['chapters'].pop()
        with self.assertRaises(ValidationError):
            Draft202012Validator(planning_schema(OUTLINE)).validate(raw)
        raw=outline_fixture()
        raw.pop('characters')
        with self.assertRaises(ValidationError):
            Draft202012Validator(planning_schema(OUTLINE)).validate(raw)


class IndependentChapterChecks(unittest.TestCase):
    def test_chapters_run_out_of_order_and_assembly_requires_all_matching_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch('story_plan.ask',return_value=outline_fixture()):
                prepare_outline(root,'story-test',[])
            draft=(root/'story-draft.json').read_bytes()
            with patch('story_plan.ask',side_effect=lambda schema,*a,**k:slot_response(schema)) as model:
                for index in (5,1,3,0,4):
                    write_chapter(root,'story-test',index)
                self.assertEqual((root/'story-draft.json').read_bytes(),draft)
                with self.assertRaisesRegex(StoryValidationError,'missing_chapter'):
                    assemble_story(root,'story-test',[])
                write_chapter(root,'story-test',2)
                self.assertEqual(model.call_count,6)
                write_chapter(root,'story-test',5)
                self.assertEqual(model.call_count,6)
            story=assemble_story(root,'story-test',[])
            self.assertEqual(len(story['scenes']),48)
            self.assertEqual(story['scenes'][0]['index'],0)
            self.assertEqual(story['scenes'][-1]['index'],47)
            self.assertTrue(1100<=len(story['lyrics'].split())<=1500)

    def test_cli_outline_chapter_and_assembly_handoff_without_sequential_generation(self):
        from daily_story import main
        import sys
        def response(schema,*args,**kwargs):
            return outline_fixture() if schema==OUTLINE else slot_response(schema)
        with tempfile.TemporaryDirectory() as temporary,contextlib.chdir(temporary),patch('story_plan.ask',side_effect=response):
            for stage,index in [('outline',None),('chapter',4),('chapter',0),('chapter',5),('chapter',1),('chapter',3),('chapter',2),('assemble',None)]:
                argv=['daily_story.py','--run-id','story-test','--stage',stage]
                if index is not None:
                    argv+=['--part',str(index)]
                with patch.object(sys,'argv',argv):
                    main()
            story=json.loads(Path('output/story-test/story.json').read_text())
            self.assertEqual(story['run_id'],'story-test')
            self.assertEqual(len(story['scenes']),48)

    def test_rejects_cross_story_checkpoint_before_any_model_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            save_json(root/'story-draft.json',dict(run_id='another-story',outline=outline_fixture()))
            with patch('story_plan.ask') as model,self.assertRaisesRegex(StoryValidationError,'identity'):
                write_chapter(root,'story-test',0)
            model.assert_not_called()

    def test_bad_scene_keeps_good_scenes_and_resumes_only_missing_slot(self):
        from story_plan import REPAIR_REQUESTS
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            save_json(root/'story-draft.json',dict(run_id='story-test',outline=outline_fixture()))
            requested=[]
            def bad_response(schema,*args,**kwargs):
                requested.append(set(schema['properties']))
                response=slot_response(schema)
                if 'scene_2' in response:
                    response['scene_2']['text']='Invalid English narration'
                return response
            with patch('story_plan.ask',side_effect=bad_response) as model:
                with self.assertRaises(StoryValidationError) as error:
                    write_chapter(root,'story-test',0)
                self.assertEqual(error.exception.code,'chapter_scene_repair_incomplete')
                self.assertEqual(model.call_count,REPAIR_REQUESTS)
                self.assertEqual(error.exception.details['pending_scenes'],[3])
            self.assertEqual(len(requested[0]),8)
            self.assertTrue(all(keys=={'scene_2'} for keys in requested[1:]))
            progress=json.loads((root/'chapters/progress-0.json').read_text())
            preserved=copy.deepcopy(progress['accepted'])
            self.assertEqual(len(preserved),7)
            self.assertFalse((root/'chapters/chapter-0.json').exists())
            self.assertNotIn('Invalid English narration',(root/'chapters/validation-0.json').read_text())
            with patch('story_plan.ask',side_effect=lambda schema,*a,**k:slot_response(schema)) as model:
                write_chapter(root,'story-test',0)
                model.assert_called_once()
                self.assertEqual(set(model.call_args.args[0]['properties']),{'scene_2'})
            complete=json.loads((root/'chapters/chapter-0.json').read_text())
            for key,value in preserved.items():
                self.assertEqual(complete['scenes'][int(key)],value)


class WorkflowConcurrencyChecks(unittest.TestCase):
    def test_dependency_graph_keeps_independent_work_parallel(self):
        jobs=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())['jobs']
        self.assertEqual(jobs['images']['strategy']['matrix']['shard'],list(range(18)))
        self.assertEqual(jobs['images']['strategy']['max-parallel'],18)
        self.assertEqual(jobs['images']['env']['IMAGE_SHARDS'],'18')
        self.assertEqual(jobs['chapters']['needs'],'outline')
        self.assertEqual(jobs['chapters']['strategy']['matrix']['chapter'],list(range(6)))
        self.assertEqual(jobs['music']['needs'],'plan')
        self.assertEqual(jobs['music']['strategy']['matrix']['part'],list(range(6)))
        self.assertEqual(jobs['voice']['needs'],'plan')
        self.assertNotIn('music',jobs['render']['needs'])
        self.assertEqual(jobs['render']['strategy']['max-parallel'],18)
        self.assertNotIn('render',jobs['mix']['needs'])
        self.assertIn('mix',jobs['publish']['needs'])
        self.assertIn('render',jobs['publish']['needs'])
        self.assertTrue(any('--prepared-clips' in step.get('run','') for step in jobs['publish']['steps']))

    def test_all_48_images_are_generated_once_across_18_workers_and_reused(self):
        from PIL import Image
        from story_video import generate_images
        story=example_story()
        def generate(prompt,path,**kwargs):
            Image.new('RGB',(32,24),'gold').save(path)
        with tempfile.TemporaryDirectory() as temporary,patch('story_image_cpu.generate',side_effect=generate) as model:
            root=Path(temporary)
            counts=[]
            for shard in range(18):
                with patch.dict(os.environ,{'IMAGE_SHARD':str(shard),'IMAGE_SHARDS':'18'}):
                    generate_images(root,story)
                counts.append(len(json.loads((root/f'image-manifest-{shard:02d}.json').read_text())))
            self.assertEqual(model.call_count,48)
            self.assertEqual(counts,[3]*12+[2]*6)
            for shard in range(18):
                with patch.dict(os.environ,{'IMAGE_SHARD':str(shard),'IMAGE_SHARDS':'18'}):
                    generate_images(root,story)
            self.assertEqual(model.call_count,48)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg media smoke checks')
class ParallelMediaChecks(unittest.TestCase):
    def test_six_independent_score_parts_mix_to_measured_voice_without_rewriting_voice(self):
        from daily_story import generate_score_part,mix_score
        from story_media import digest
        from pipeline import duration
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            story=example_story()
            source=root/'source.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=200:sample_rate=24000:duration=120',str(source)],check=True)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=24000:duration=480',str(root/'narration.wav')],check=True)
            original=digest(root/'narration.wav')
            def synthesize(request,target,*args):
                self.assertTrue(request['instrumental'])
                self.assertEqual(request['duration'],120)
                shutil.copyfile(source,target)
            with patch('story_music_cpu.generate_segment',side_effect=synthesize) as model:
                for part in (5,2,0,4,1,3):
                    generate_score_part(root,story,part)
                self.assertEqual(model.call_count,6)
            timing=dict(duration=480,scenes=[dict(index=i,start=i*10,end=(i+1)*10) for i in range(48)])
            mix_score(root,story,timing)
            self.assertAlmostEqual(duration(root/'song.wav'),480,places=2)
            self.assertAlmostEqual(duration(root/'background.wav'),720,places=2)
            self.assertEqual(digest(root/'narration.wav'),original)
            manifest=root/'score/part-2/request.json'
            saved=json.loads(manifest.read_text());saved['story_hash']='another-story';save_json(manifest,saved)
            with self.assertRaisesRegex(ValueError,'mismatched'):
                mix_score(root,story,timing)

    def test_parallel_render_join_uses_verified_clips_and_rejects_stale_images(self):
        from PIL import Image
        from story_video import render_clips,render
        from pipeline import duration
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            story=dict(scenes=[dict(index=0),dict(index=1)])
            timing=dict(duration=480,scenes=[dict(index=0,start=0,end=240),dict(index=1,start=240,end=480)])
            save_json(root/'story.json',story);save_json(root/'timing.json',timing)
            for i,color in enumerate(('blue','gold')):
                Image.new('RGB',(128,72),color).save(root/f'scene-{i:03d}-source.png')
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=24000:duration=480',str(root/'song.wav')],check=True)
            render_clips(root,story,timing,width=128,height=72,shard=1,shards=18)
            render_clips(root,story,timing,width=128,height=72,shard=0,shards=18)
            with patch('story_video.render_clips',side_effect=AssertionError('Do not re-render during join')):
                render(root,story,timing,width=128,height=72,prepared_clips=True)
            self.assertEqual(duration(root/'video.mp4'),480)
            Image.new('RGB',(128,72),'red').save(root/'scene-001-source.png')
            with self.assertRaisesRegex(ValueError,'stale'):
                render(root,story,timing,width=128,height=72,prepared_clips=True)


if __name__=='__main__':
    unittest.main()
