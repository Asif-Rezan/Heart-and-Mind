"""Planning fan-out, immutable prose joins and the one-minute editorial budget failure."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml
from story_writer import save_json,validate_story,StoryValidationError
from story_planning import run_worker,join_planning,visual_indices,visual_worker_count
from story_engagement import polish_engagement
from test_short_story import short_story
from test_visual_support import record_for
from test_pipeline_sample import sample_story


def prose_fixture(sample=False):
    story=sample_story() if sample else short_story()
    for field in ('visuals','thumbnail_scene','thumbnail_prompt'):story.pop(field)
    return story


def planning_response(schema,prompt,*args,**kwargs):
    fields=schema['properties']
    import re
    # Read the supplied final narration, never supply a paraphrased evidence quote.
    beats=json.loads(prompt.split('Final spoken beats: ')[1] if 'Final spoken beats: ' in prompt else prompt.split('Final chronological beats for this batch: ')[1].split('\nRequested indices:')[0])
    text_by_index={b['index']:b['text'] for b in beats}
    def record(index):
        return dict(prompt='Ram in his blue kurta reads a letter at the counter inside his familiar village shop.',
                    evidence=text_by_index[index][:300],checks=[dict(question='What is the man reading?',answers=['letter','paper'])])
    if 'scene' in fields:
        return dict(scene=5,visual=record(5),viewer_question='What decision will this letter make Ram reconsider?')
    return {key:record(int(key.split('_')[1])) for key in fields}


def seo_response(*args,**kwargs):
    return dict(title='एक चिट्ठी से बदला फैसला | Hindi Story',description='एक चिट्ठी ने दुकानदार को अपने परिवार के बारे में फिर से सोचने पर मजबूर किया। '*5,
                tags=['Hindi Story','Emotional Hindi Story','परिवार की कहानी','चिट्ठी की कहानी','Chitthi ki kahani','Heart and Mind','Family Story','Motivational Kahani'])


class ParallelPlanning(unittest.TestCase):
    def prepare(self,root,sample=False):
        story=prose_fixture(sample);save_json(root/'story-prose.json',story);return story

    def workers(self,root,story):
        with patch('story_plan.ask',side_effect=planning_response),patch('story_packaging.ask',side_effect=seo_response):
            # Different completion order must not change the final spoken script.
            for part in reversed(range(visual_worker_count(story))):run_worker(root,story['run_id'],'visual',part)
            run_worker(root,story['run_id'],'thumbnail')
            run_worker(root,story['run_id'],'seo')

    def test_release_has_eighteen_nonempty_workers_sample_uses_twelve(self):
        for sample,expected in ((False,18),(True,12)):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);story=self.prepare(root,sample)
                self.assertEqual(visual_worker_count(story),expected)
                indices=[i for part in range(expected) for i in visual_indices(story,part)]
                self.assertEqual(indices,list(range(len(story['scenes']))))
                before=(root/'story-prose.json').read_bytes()
                self.workers(root,story)
                result=join_planning(root,story['run_id']);validate_story(result)
                self.assertEqual(result['lyrics'],story['lyrics'])
                self.assertEqual(result['scenes'],story['scenes'])
                self.assertEqual((root/'story-prose.json').read_bytes(),before)
                self.assertEqual(len(result['visuals']),len(story['scenes']))
                self.assertEqual(json.loads((root/'planning-join.json').read_text())['workers'],expected+2)

    def test_join_rejects_missing_stale_and_script_replacement_payloads(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);story=self.prepare(root)
            with self.assertRaisesRegex(StoryValidationError,'planning_output_missing'):join_planning(root,story['run_id'])
            self.workers(root,story)
            path=root/'planning-visual-17.json';saved=json.loads(path.read_text());valid=copy.deepcopy(saved)
            saved['prose_identity']='stale';save_json(path,saved)
            with self.assertRaisesRegex(StoryValidationError,'planning_output_identity_mismatch'):join_planning(root,story['run_id'])
            save_json(path,valid)
            path=root/'planning-seo.json';saved=json.loads(path.read_text());saved['payload']['scenes']=[];save_json(path,saved)
            with self.assertRaisesRegex(StoryValidationError,'planning_payload_invalid'):join_planning(root,story['run_id'])
            self.assertFalse((root/'story.json').exists())

    def test_completed_workers_resume_without_model_calls_and_only_corrupt_worker_replans(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);story=self.prepare(root);self.workers(root,story)
            with patch('story_plan.ask',side_effect=AssertionError('Do not regenerate')):
                run_worker(root,story['run_id'],'visual',0)
                run_worker(root,story['run_id'],'thumbnail')
            path=root/'planning-visual-0.json';data=json.loads(path.read_text());data['payload']={};save_json(path,data)
            with patch('story_plan.ask',side_effect=planning_response) as model:run_worker(root,story['run_id'],'visual',0)
            model.assert_called_once()

    def test_workflow_fanout_and_join_are_real_independent_github_jobs(self):
        for filename in ('stories.yml','story-plan-preview.yml'):
            jobs=yaml.safe_load((Path('.github/workflows')/filename).read_text())['jobs']
            for name in ('planning_seo','planning_thumbnail','planning_visuals'):
                self.assertEqual(jobs[name]['needs'],'prose')
            self.assertEqual(jobs['planning_visuals']['strategy']['max-parallel'],18)
            self.assertIn('fromJSON(needs.prose.outputs.visual_parts)',jobs['planning_visuals']['strategy']['matrix']['part'])
            self.assertTrue(set(('prose','planning_seo','planning_thumbnail','planning_visuals')).issubset(jobs['plan']['needs']))
            self.assertFalse(any('requirements-lyrics' in step.get('run','') for step in jobs['plan']['steps']))
            self.assertIn('visual_parts',jobs['prose']['outputs'])


class SampleEditorialBudget(unittest.TestCase):
    def prepared(self):
        story=sample_story()
        # Replay the actual failed total (162), scene-1 length (13), scene-2 length (11).
        story['scenes'][2]['text']=' '.join(story['scenes'][2]['text'].split()[:11])+'।'
        total=sum(len(s['text'].split()) for s in story['scenes'])
        story['scenes'][0]['text']+=' '+' '.join(['सुबह']*(162-total))
        story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
        return story

    def test_overlong_edits_get_budget_reason_and_next_request_has_exact_caps(self):
        story=self.prepared();self.assertEqual(len(story['lyrics'].split()),162)
        review=dict(hook=True,progression=False,payoff=True,cta=True,
                    repairs=[dict(scene=i,instruction='Clarify this existing action without adding exposition.') for i in (1,2)])
        long={f'scene_{i}':dict(text=' '.join(story['scenes'][i]['text'].split()+['शाम']*16),visual=story['scenes'][i]['visual']) for i in (1,2)}
        fixed={f'scene_{i}':dict(text='कल '+' '.join(story['scenes'][i]['text'].split()[1:]),visual=story['scenes'][i]['visual']) for i in (1,2)}
        with tempfile.TemporaryDirectory() as folder,patch('story_engagement.ask',side_effect=[review,long,fixed]) as model:
            polish_engagement(Path(folder),story)
            self.assertEqual(model.call_count,3)
            self.assertIn('story_word_budget',model.call_args.args[1])
            self.assertIn('Per-scene word limits',model.call_args.args[1])
            self.assertEqual(len(story['lyrics'].split()),162)
            self.assertEqual(json.loads((Path(folder)/'engagement-review.json').read_text())['complete'],['1','2'])

    def test_persistent_bad_edits_report_why_without_accepting_overlong_sample(self):
        story=self.prepared()
        review=dict(hook=True,progression=False,payoff=True,cta=True,repairs=[dict(scene=1,instruction='Clarify the existing conflict briefly.')])
        long={'scene_1':dict(text=' '.join(story['scenes'][1]['text'].split()+['शाम']*16),visual=story['scenes'][1]['visual'])}
        with tempfile.TemporaryDirectory() as folder,patch('story_engagement.ask',side_effect=[review,long,long]),self.assertRaises(StoryValidationError) as stopped:
            polish_engagement(Path(folder),story)
        self.assertEqual(stopped.exception.details['rejections']['1']['reason'],'story_word_budget')
        self.assertEqual(len(story['lyrics'].split()),162)
