"""Reject ungrounded plans, missing story anchors and stale accepted-image caches."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from story_visual_contract import validate_contract, require_visuals
from story_image_review import generate_reviewed, cache_current, digest, matches
from test_visual_support import record_for,passed_review,attach_contracts,PLAN_VERDICT
from test_short_story import short_story


class StoryVisualChecks(unittest.TestCase):
    def test_nested_visual_records_normalize_prompt_only_and_preserve_exact_evidence(self):
        from story_writer import planning_schema,normalize_planning,object_schema
        from story_visual_contract import contract_schema
        schema=object_schema({'visual':contract_schema()})
        record=record_for(dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and begins reading beside the counter.'))
        record['prompt']+=' Additional setting detail.'*30
        inferred=planning_schema(schema)
        self.assertNotIn('maxLength',inferred['properties']['visual']['properties']['prompt'])
        self.assertEqual(inferred['properties']['visual']['properties']['evidence']['maxLength'],360)
        fixed=normalize_planning({'visual':record},schema)['visual']
        self.assertLessEqual(len(fixed['prompt']),360)
        self.assertEqual(fixed['evidence'],record['evidence'])
        self.assertEqual(fixed['checks'],record['checks'])

    def test_invented_plan_is_rejected_and_replanned_before_any_image_generation(self):
        from story_plan import visual_batch
        story=short_story();first=record_for(story['scenes'][0],'A shopkeeper opens a magical treasure chest inside his village shop.')
        corrected=record_for(story['scenes'][0],'A shopkeeper opens his actual story letter beside the village shop counter.')
        rejected=PLAN_VERDICT.copy();rejected.update(faithful=False,issues=['The chest is not in the narrated scene.'])
        with tempfile.TemporaryDirectory() as folder,patch('story_plan.ask',side_effect=[
                {'scene_0':first},rejected,{'scene_0':corrected},PLAN_VERDICT.copy()]) as model:
            result=visual_batch(Path(folder),story,[0],'1234567')
            self.assertEqual(model.call_count,4)
            self.assertIn('chest is not',model.call_args_list[2].args[1])
            self.assertTrue(result['0']['planning_review']['passed'])
            self.assertTrue(result['0']['prompt'].startswith(corrected['event']))

    def test_composition_schema_enforces_english_and_count_answers_match_digits(self):
        from jsonschema import Draft202012Validator
        from story_visual_contract import composition_schema
        record=record_for(dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and begins reading beside the counter.'))
        raw={k:v for k,v in record.items() if k not in ('prompt','planning_review')}
        raw['literal_scene']='The man opens a letter and starts reading.'
        schema=composition_schema();self.assertTrue(Draft202012Validator(schema).is_valid(raw))
        raw['event']='उसने चिट्ठी खोलकर पढ़ना शुरू किया।'
        self.assertFalse(Draft202012Validator(schema).is_valid(raw))
        self.assertTrue(matches('2',['two']))
        self.assertFalse(matches('3',['two']))

    def test_plan_audit_accepts_rejection_even_if_one_individual_criterion_passes(self):
        import sys
        import preview_story_artwork
        verdict=dict(version='test',passed=False,verdict=dict(faithful=True,checks_observable=False))
        with tempfile.TemporaryDirectory() as folder,patch.object(sys,'argv',['preview','--stage','audit-plan','--output',folder]),patch('story_visual_contract.assess_plan',return_value=verdict):
            preview_story_artwork.main()
            self.assertFalse(json.loads((Path(folder)/'rejected-plan-review.json').read_text())['passed'])

    def test_paraphrased_or_other_scene_evidence_is_rejected(self):
        scene=dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and begins reading beside the counter.')
        record=record_for(scene)
        validate_contract(record,scene)
        record['evidence']='उसने एक जादुई खजाना खोला।'
        with self.assertRaisesRegex(ValueError,'visual_evidence_not_in_scene'):validate_contract(record,scene)

    def test_yes_no_confirmation_questions_are_not_a_semantic_gate(self):
        scene=dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and begins reading beside the counter.')
        record=record_for(scene);record['checks']=[dict(question='Is there a letter?',answers=['yes'])]
        with self.assertRaisesRegex(ValueError,'visual_question_not_open'):validate_contract(record,scene)
        self.assertFalse(matches('nothing',['letter']))
        self.assertFalse(matches('no letter',['letter']))
        self.assertFalse(matches('newsletter',['letter']))
        self.assertFalse(matches('man without a letter',['letter']))
        self.assertFalse(matches('a man',['चिट्ठी']))
        self.assertTrue(matches('letters',['letter']))
        self.assertTrue(matches('a sealed envelope',['letter','envelope']))

    def test_old_plan_or_changed_prose_cannot_be_used_for_new_generation(self):
        story=short_story()
        with self.assertRaisesRegex(ValueError,'visual_plan_outdated'):require_visuals(story)
        attach_contracts(story);require_visuals(story)
        story['scenes'][0]['text']='यह बिल्कुल अलग कहानी है।'
        with self.assertRaisesRegex(ValueError,'visual_evidence_not_in_scene'):require_visuals(story)

    def test_failed_candidate_is_retried_and_only_checked_pixels_are_accepted(self):
        calls=[]
        def draw(prompt,path,**kwargs):
            calls.append((prompt,kwargs))
            Image.new('RGB',(1344,768),'red' if len(calls)==1 else 'blue').save(path)
        def review(path,checks):
            with Image.open(path) as im:self.assertEqual(im.size,(1920,1080))
            result=passed_review(path,checks);result['passed']=len(calls)>1
            return result
        contract=record_for(dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and begins reading beside the counter.'))
        with tempfile.TemporaryDirectory() as folder,patch('story_image_cpu.generate',side_effect=draw),patch('story_image_review.review_image',side_effect=review):
            target=Path(folder)/'thumbnail-source.png'
            report=generate_reviewed('Show the story letter being opened.',target,42,contract,kind='thumbnail')
            self.assertEqual([kw['seed'] for _,kw in calls],[42,7961])
            self.assertTrue(report['passed'])
            self.assertEqual(report['source_sha256'],digest(target))
            with Image.open(target) as image:self.assertEqual(image.getpixel((100,100)),(0,0,255))
            plan=dict(prompt='current story composition',contract=contract)
            saved=dict(plan,review=report)
            self.assertTrue(cache_current(saved,plan,target))
            Image.new('RGB',(1344,768),'green').save(target)
            self.assertFalse(cache_current(saved,plan,target))

    def test_generation_and_review_service_failures_do_not_stop_images(self):
        contract=record_for(dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and begins reading beside the counter.'))
        with tempfile.TemporaryDirectory() as folder,patch('story_image_cpu.generate',side_effect=RuntimeError('offline')) as model:
            target=Path(folder)/'scene.png'
            report=generate_reviewed('Read the letter.',target,42,contract,width=640,height=360)
            self.assertEqual(model.call_count,2)
            self.assertEqual(report['fallback'],'neutral-background')
            self.assertFalse(report['passed'])
            with Image.open(target) as im:self.assertEqual(im.size,(640,360))
            plan=dict(prompt='current composition',contract=contract)
            self.assertTrue(cache_current(dict(plan,review=report),plan,target))
        def draw(prompt,path,**kwargs):Image.new('RGB',(640,360),'blue').save(path)
        with tempfile.TemporaryDirectory() as folder,patch('story_image_cpu.generate',side_effect=draw),patch('story_image_review.review_image',side_effect=RuntimeError('unavailable')):
            target=Path(folder)/'scene.png'
            report=generate_reviewed('Read the letter.',target,42,contract)
            self.assertEqual(report['fallback'],'best-candidate')
            self.assertTrue(target.exists())

    def test_planning_service_failure_returns_honest_neutral_contracts(self):
        from story_plan import visual_batch,thumbnail_plan
        from story_visual_contract import is_fallback
        story=short_story()
        with tempfile.TemporaryDirectory() as folder,patch('story_plan.ask',side_effect=RuntimeError('offline')):
            records=visual_batch(Path(folder),story,[0,1],'1234567')
            self.assertEqual(set(records),{'0','1'})
            self.assertTrue(all(is_fallback(r) and not r['planning_review']['passed'] for r in records.values()))
            thumb=thumbnail_plan(Path(folder),story,'1234567')
            self.assertTrue(is_fallback(thumb['thumbnail_contract']))

    def test_fictional_name_in_vqa_is_rejected_without_model_review(self):
        scene=dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and reads it.')
        record=record_for(scene);record['people']='Arjun, 38, brown shirt'
        record['prompt']=__import__('story_visual_contract').compile_contract(record)['prompt']
        record['checks']=[dict(question='Who opens the letter?',answers=['Arjun'])]
        with self.assertRaisesRegex(ValueError,'fictional_name'):validate_contract(record,scene)

    def test_unsupported_details_override_positive_review_flags(self):
        from story_visual_contract import assess_plan
        record=record_for(dict(text='वह नाराज था।',visual='The man throws a broken toy into a pile.'))
        verdict=dict(PLAN_VERDICT,source_translation='He was angry.',unsupported_details=['Throwing a toy is not narrated.'])
        review=assess_plan(record,dict(text='वह नाराज था।'),'A man','Village',1,None,ask_fn=lambda *a,**kw:verdict)
        self.assertFalse(review['passed'])

    def test_all_rejected_candidates_keep_best_image_with_explicit_warning(self):
        def draw(prompt,path,**kwargs):Image.new('RGB',(64,36),'gold').save(path)
        def reject(path,checks):
            result=passed_review(path,checks);result['passed']=False
            return result
        contract=record_for(dict(text='उसने चिट्ठी खोली और चुपचाप पढ़ने लगा।',visual='The man opens a letter and begins reading beside the counter.'))
        with tempfile.TemporaryDirectory() as folder,patch('story_image_cpu.generate',side_effect=draw) as model,patch('story_image_review.review_image',side_effect=reject):
            target=Path(folder)/'scene.png'
            report=generate_reviewed('Read the letter.',target,42,contract)
            self.assertFalse(report['passed'])
            self.assertEqual(report['fallback'],'best-candidate')
            self.assertEqual(model.call_count,2)
            self.assertTrue(target.exists())
            reports=json.loads((Path(folder)/'image-review'/'scene'/'reviews.json').read_text())
            self.assertEqual(len(reports),2)
