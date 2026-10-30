"""Replay the failed production shapes without storing the private story prose."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator,ValidationError

from story_plan import (DEFAULT_ROLES,chapter_issues,scene_issues,scene_schema,recovered_roles,
                        write_chapter,assemble_story,outline_identity,repair_indices)
from story_writer import save_json,validate_story,planning_schema,normalize_planning
from test_story_parallel import outline_fixture,slot_response

# Exact counts/speaker patterns of the six production chapters, with deidentified
# synthetic prose. Indices 0 and 1 correspond to the two user-reported jobs.
PROFILES=[
 ([28,24,22,20,28,22,16,17],['narrator','narrator','male','female','narrator','narrator','male','female']),
 ([28,22,30,31,26,34,29,30],['narrator','narrator','male','female','narrator','narrator','male','female']),
 ([28,28,27,24,25,27,27,25],['narrator','narrator','narrator','narrator','female','male','narrator','narrator']),
 ([34,35,22,18,29,28,23,23],['narrator','narrator','female','male','narrator','narrator','narrator','narrator']),
 ([20,18,17,16,17,17,17,18],['narrator','narrator','male','female','narrator','narrator','male','female']),
 ([33,31,29,33,27,24,26,25],['narrator','narrator','female','male','narrator','narrator','female','male']),
]


def rows_for(profile):
    words,roles=profile
    return [dict(speaker=role,text=' '.join(['कहानी']*count)+'।',
                 visual='An Indian family talks in a beautiful village courtyard.') for count,role in zip(words,roles)]


class ProductionChapterRegression(unittest.TestCase):
    def test_all_failed_production_profiles_recover_without_discarding_accepted_prose(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            draft=dict(run_id='story-test',outline=outline_fixture())
            save_json(root/'story-draft.json',draft)
            for i,profile in enumerate(PROFILES):
                save_json(root/'chapters'/f'raw-{i}.json',dict(scenes=rows_for(profile)))
            # The one successful old chapter must not be generated again.
            successful=root/'chapters/chapter-2.json'
            save_json(successful,dict(scenes=rows_for(PROFILES[2]),index=2,outline_hash=outline_identity(draft)))
            original=successful.read_bytes()
            calls=[]
            def inference(schema,*args,**kwargs):
                calls.append(set(schema['properties']))
                response=slot_response(schema)
                Draft202012Validator(schema).validate(response)
                return response
            with patch('story_plan.ask',side_effect=inference):
                for i in range(6):
                    write_chapter(root,'story-test',i)
            self.assertEqual(successful.read_bytes(),original)
            self.assertEqual(calls,[{'scene_6','scene_7'},{'scene_6','scene_7'},
                                    {'scene_4','scene_5','scene_6','scene_7'},{'scene_6','scene_7'}])
            self.assertEqual(sum(map(len,calls)),10)
            for i,profile in enumerate(PROFILES):
                rows=rows_for(profile)
                roles=recovered_roles(rows)
                result=json.loads((root/'chapters'/f'chapter-{i}.json').read_text())
                self.assertIsNone(chapter_issues(result))
                for position,row in enumerate(rows):
                    if not scene_issues(row,roles[position]):
                        self.assertEqual(result['scenes'][position],row)
            story=assemble_story(root,'story-test',[])
            validate_story(story)
            self.assertEqual(len(story['scenes']),48)
            self.assertEqual(sum(s['speaker']=='narrator' for s in story['scenes']),36)
            self.assertTrue(1000<=len(story['lyrics'].split())<=1600)

    def test_speaker_counts_are_determined_before_prose_not_by_model(self):
        schema=scene_schema(range(8))
        response=slot_response(schema)
        Draft202012Validator(schema).validate(response)
        self.assertEqual(DEFAULT_ROLES.count('narrator'),6)
        for spec in schema['properties'].values():
            self.assertNotIn('speaker',spec['properties'])
        response['scene_0']['speaker']='male'
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema).validate(response)

    def test_scene_slot_visual_is_bounded_without_changing_speech(self):
        schema=scene_schema([2])
        response=slot_response(schema)
        speech=response['scene_2']['text']
        response['scene_2']['visual']='A complete visual planning sentence in English. '*40
        Draft202012Validator(planning_schema(schema)).validate(response)
        bounded=normalize_planning(response,schema)
        self.assertEqual(bounded['scene_2']['text'],speech)
        self.assertLessEqual(len(bounded['scene_2']['visual']),360)
        self.assertEqual(planning_schema(schema)['properties']['scene_2']['properties']['text']['maxLength'],400)

    def test_natural_short_dialogue_and_33_word_narration_are_valid(self):
        short=rows_for(([12],['female']))[0]
        self.assertEqual(scene_issues(short),[])
        narration=rows_for(([33],['narrator']))[0]
        self.assertEqual(scene_issues(narration),[])
        self.assertIn('speaker',scene_issues(short,'narrator'))
        self.assertIn('words',scene_issues(rows_for(([45],['narrator']))[0]))

    def test_budget_repairs_only_selected_scene_and_never_truncates_existing_prose(self):
        accepted={str(i):s for i,s in enumerate(rows_for(([18]*6+[8]*2,
                       ['narrator']*6+['male','female'])))}
        before=copy.deepcopy(accepted)
        selected=repair_indices(accepted)
        self.assertTrue(0<len(selected)<8)
        self.assertEqual(accepted,before)

    def test_cross_outline_partial_checkpoint_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            save_json(root/'story-draft.json',dict(run_id='story-test',outline=outline_fixture()))
            save_json(root/'chapters/progress-0.json',dict(run_id='story-test',outline_hash='other-outline'))
            with patch('story_plan.ask') as model,self.assertRaisesRegex(ValueError,'identity_mismatch'):
                write_chapter(root,'story-test',0)
            model.assert_not_called()


if __name__=='__main__':
    unittest.main()
