"""Assembly repairs aggregate prose budgets without relaxing publication checks."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lyrics_cpu import StoryGenerationError
from story_plan import assemble_story, outline_identity, StoryValidationError
from story_writer import save_json
from test_story_parallel import outline_fixture, chapter_fixture


class StoryBudgetRepairChecks(unittest.TestCase):
    def prepare(self, root, words):
        draft=dict(run_id='story-test',outline=outline_fixture())
        save_json(root/'story-draft.json',draft)
        for i in range(6):
            chapter=chapter_fixture()
            for scene in chapter['scenes']:
                scene['text']=' '.join(['कहानी']*words)+'।'
            save_json(root/'chapters'/f'chapter-{i}.json',dict(
                chapter,index=i,outline_hash=outline_identity(draft)))

    def response(self, schema, *args, **kwargs):
        return {key:dict(text=' '.join(['कहानी']*27)+'।') for key in schema['properties']}

    def test_short_and_long_stories_repair_and_resume_without_model_calls(self):
        for words in (10,40):
            with self.subTest(words=words),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)
                self.prepare(root,words)
                original=[json.loads(p.read_text()) for p in sorted((root/'chapters').glob('chapter-*.json'))]
                with patch('story_plan.ask',side_effect=self.response) as model:
                    story=assemble_story(root,'story-test',[])
                    self.assertGreater(model.call_count,0)
                self.assertTrue(1000<=len(story['lyrics'].split())<=1600)
                for i,scene in enumerate(story['scenes']):
                    before=original[i//8]['scenes'][i%8]
                    self.assertEqual(scene['speaker'],before['speaker'])
                    self.assertEqual(scene['visual'],before['visual'])
                # Recovery also works if interruption happened before manifest save.
                (root/'story.json').unlink()
                with patch('story_plan.ask',side_effect=AssertionError('Regeneration')):
                    resumed=assemble_story(root,'story-test',[])
                self.assertEqual(resumed,story)

    def test_transient_failure_retries_and_invalid_prose_is_never_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            self.prepare(root,20)
            responses=[StoryGenerationError('temporary'),{'scene_0':dict(text='English only')}]
            def response(schema,*args,**kwargs):
                if responses:
                    item=responses.pop(0)
                    if isinstance(item,Exception):
                        raise item
                    return item
                return self.response(schema)
            with patch('story_plan.ask',side_effect=response) as model:
                story=assemble_story(root,'story-test',[])
            self.assertGreaterEqual(model.call_count,3)
            self.assertNotIn('English',story['lyrics'])
            self.assertFalse(json.loads((root/'story-budget-repair.json').read_text())['pending'])

    def test_exhaustion_is_bounded_and_diagnostic_without_publishing_invalid_story(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            self.prepare(root,10)
            before=(root/'chapters/chapter-0.json').read_bytes()
            with patch('story_plan.ask',return_value={}) as model:
                with self.assertRaises(StoryValidationError) as caught:
                    assemble_story(root,'story-test',[])
            self.assertEqual(model.call_count,12)
            self.assertEqual(caught.exception.code,'story_budget_repair_incomplete')
            self.assertEqual(caught.exception.details['total_words'],480)
            self.assertFalse((root/'story.json').exists())
            self.assertEqual((root/'chapters/chapter-0.json').read_bytes(),before)

    def test_valid_budget_and_invalid_identity_never_call_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            self.prepare(root,25)
            with patch('story_plan.ask') as model:
                assemble_story(root,'story-test',[])
                model.assert_not_called()
                with self.assertRaisesRegex(StoryValidationError,'identity'):
                    assemble_story(root,'different-story',[])

    def test_interrupted_repair_keeps_gains_and_uses_new_seed_on_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            self.prepare(root,10)
            seeds=[]
            def interrupted(schema,prompt,seed,*args,**kwargs):
                seeds.append(seed)
                if len(seeds)==2:
                    raise KeyboardInterrupt()
                return self.response(schema)
            with patch('story_plan.ask',side_effect=interrupted),self.assertRaises(KeyboardInterrupt):
                assemble_story(root,'story-test',[])
            repaired=(root/'chapters/chapter-0.json').read_bytes()
            def resumed(schema,prompt,seed,*args,**kwargs):
                self.assertNotIn(seed,seeds)
                return self.response(schema)
            with patch('story_plan.ask',side_effect=resumed):
                story=assemble_story(root,'story-test',[])
            self.assertEqual((root/'chapters/chapter-0.json').read_bytes(),repaired)
            self.assertGreaterEqual(len(story['lyrics'].split()),1000)

    def test_workflow_installs_repair_runtime_and_keeps_failed_checkpoints(self):
        import yaml
        job=yaml.safe_load(Path('.github/workflows/stories.yml').read_text())['jobs']['plan']
        self.assertTrue(any('requirements-lyrics.txt' in step.get('run','') for step in job['steps']))
        self.assertEqual(job['steps'][-1]['if'],'always()')
        self.assertGreaterEqual(job['timeout-minutes'],90)

    def test_run7_actual_word_profile_recovers_from_780_words(self):
        # Counts only from production; no private story prose is stored here.
        profiles=[[23,16,13,17,12,10,16,16],[20,19,7,16,15,12,15,16],
                  [23,17,17,22,18,13,18,21],[26,24,10,18,17,18,20,24],
                  [12,13,16,16,15,6,12,14],[14,16,14,18,17,19,14,15]]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            self.prepare(root,20)
            for i,counts in enumerate(profiles):
                path=root/'chapters'/f'chapter-{i}.json'
                chapter=json.loads(path.read_text())
                for scene,count in zip(chapter['scenes'],counts):
                    scene['text']=' '.join(['कहानी']*count)+'।'
                save_json(path,chapter)
            with patch('story_plan.repair_story_budget'),self.assertRaises(StoryValidationError) as caught:
                assemble_story(root,'story-test',[])
            self.assertEqual(caught.exception.code,'story_word_budget')
            self.assertEqual(caught.exception.details['total_words'],780)
            with patch('story_plan.ask',side_effect=self.response) as model:
                story=assemble_story(root,'story-test',[])
            self.assertLessEqual(model.call_count,3)
            self.assertTrue(1000<=len(story['lyrics'].split())<=1600)
