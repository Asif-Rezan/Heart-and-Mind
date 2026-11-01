"""Replay run 41291878710: English narration must be translated, never republished or blindly regenerated."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from story_plan import write_chapter,outline_identity
from story_writer import save_json,language_contract,object_schema,string
from story_format import FORMAT
from lyrics_cpu import StoryGenerationError
from test_story_parallel import outline_fixture


class LanguageRecovery(unittest.TestCase):
    def prepare(self,root):
        draft=dict(run_id='story-test',format=FORMAT,outline=outline_fixture())
        save_json(root/'story-draft.json',draft)
        visual='Arjun, blue shirt and black hair, enters the engineering office with his new identity card.'
        rows={f'scene_{i}':dict(text=f'Arjun enters office room {i} with a new ID card in hand.',visual=visual) for i in range(8)}
        save_json(root/'chapters/raw-attempt-5-5.json',rows)
        save_json(root/'chapters/progress-5.json',dict(run_id='story-test',outline_hash=outline_identity(draft),
            roles=['narrator']*8,accepted={},drafts={},requests=6))
        return rows

    def translate(self,schema,prompt,*args,**kwargs):
        self.assertIn('Translate ONLY',prompt)
        self.assertTrue(all(set(spec['properties'])=={'text'} for spec in schema['properties'].values()))
        return {key:dict(text='अर्जुन नया पहचान पत्र लेकर दफ्तर में पहुंचा और अपना काम शुरू किया।') for key in schema['properties']}

    def test_exact_eight_english_scene_failure_shape_recovers_in_two_text_only_requests(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);rows=self.prepare(root)
            with patch('story_plan.ask',side_effect=self.translate) as model:
                write_chapter(root,'story-test',5)
                self.assertEqual(model.call_count,2)
            saved=json.loads((root/'chapters/chapter-5.json').read_text())
            self.assertEqual(len(saved['scenes']),8)
            for i,scene in enumerate(saved['scenes']):
                self.assertEqual(scene['visual'],rows[f'scene_{i}']['visual'])
                self.assertIn('अर्जुन',scene['text'])
            with patch('story_plan.ask') as model:
                write_chapter(root,'story-test',5)
                model.assert_not_called()

    def test_repeated_english_translation_fails_after_two_requests_with_specific_code(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.prepare(root)
            def wrong(schema,*args,**kwargs):return {key:dict(text='Arjun enters the office again.') for key in schema['properties']}
            with patch('story_plan.ask',side_effect=wrong) as model,self.assertRaisesRegex(ValueError,'chapter_language_repair_incomplete'):
                write_chapter(root,'story-test',5)
            self.assertEqual(model.call_count,2)
            with patch('story_plan.ask',side_effect=self.translate) as model:
                write_chapter(root,'story-test',5)
                self.assertEqual(model.call_count,2)

    def test_runtime_failure_is_not_retried_as_bad_prose(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.prepare(root)
            with patch('story_plan.ask',side_effect=StoryGenerationError('CPU unavailable')) as model,self.assertRaisesRegex(ValueError,'chapter_model_runtime_failure'):
                write_chapter(root,'story-test',5)
            model.assert_called_once()

    def test_malformed_json_response_retries_only_pending_texts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.prepare(root)
            count=0
            def inference(schema,prompt,*args,**kwargs):
                nonlocal count
                count+=1
                if count==1:raise StoryGenerationError('Invalid JSON',code='story_model_response_invalid')
                return self.translate(schema,prompt)
            with patch('story_plan.ask',side_effect=inference):write_chapter(root,'story-test',5)
            self.assertEqual(count,3)

    def test_system_contract_distinguishes_spoken_text_from_english_planning(self):
        contract=language_contract(object_schema({'scene_0':object_schema({'text':string(1,400)})}))
        self.assertIn('ONLY in Hindi Devanagari',contract)
        self.assertIn('English outline is reference',contract)
        self.assertIn('English-only planning keys',language_contract(object_schema({'summary':string(1,400)})))

    def test_cli_preserves_outline_model_validation_diagnostics(self):
        import sys
        from daily_story import main
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            error=StoryGenerationError('Model response invalid after three attempts',
                code='story_model_response_invalid',details={'field':'summary','constraint':'pattern','attempt_limit':3})
            with patch.object(sys,'argv',['daily_story.py','--run-id','story-test','--stage','outline']), patch('daily_story.root_for',return_value=root), patch('story_plan.prepare_outline',side_effect=error), self.assertRaises(SystemExit):
                main()
            report=json.loads((root/'failure.json').read_text())
            self.assertEqual(report['code'],'story_model_response_invalid')
            self.assertEqual(report['details']['field'],'summary')
            self.assertEqual(report['message'],'Model response invalid after three attempts')

    def test_cli_failure_report_explains_language_error_without_generated_text(self):
        import sys
        from daily_story import main
        from story_writer import StoryValidationError
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            error=StoryValidationError('chapter_language_repair_incomplete',dict(chapter=6,pending_scenes=[1,2],attempt_limit=2))
            with patch.object(sys,'argv',['daily_story.py','--run-id','story-test','--stage','chapter','--part','5']),patch('daily_story.root_for',return_value=root),patch('story_plan.write_chapter',side_effect=error),self.assertRaises(SystemExit) as stopped:
                main()
            self.assertEqual(stopped.exception.code,1)
            report=json.loads((root/'failure.json').read_text())
            self.assertEqual(report['code'],'chapter_language_repair_incomplete')
            self.assertEqual(report['details']['pending_scenes'],[1,2])
            self.assertIn('Hindi Devanagari',report['message'])
            self.assertNotIn('Arjun',json.dumps(report))
