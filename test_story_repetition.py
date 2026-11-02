from test_visual_support import record_for
"""Regression for run 41293514297: three identical repair responses were accepted."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from story_plan import repair_repetition,prepare_visuals
from story_writer import repeated_scenes,StoryValidationError
from test_short_story import short_story

# Exact repeated narration from the failed production artifact, with no credentials.
LINES=['रात के बाद घर में शांति है, चाँद छोटे खिड़की पर टिका है।',
       "उसने एक पेज पढ़ा, फिर अगला लिखा: 'आज एक पृष्ठ। कल दो।'",
       'पुराना टीका बरकरार है, जिसमें एक रेलगाड़ी का चित्र है।']
FIXED=['अर्जुन ने घड़ी के पास अपनी कॉपी रखी और पहला सवाल समझने लगा।',
       'अगला प्रश्न कठिन निकला तो उसने पिता से मदद माँगकर हिसाब दोबारा किया।',
       'राजेश्वर ने चाय पास रखी और बेटे की कोशिश देखकर संतोष से मुस्कुराए।']


def production_echo_story():
    story=short_story()
    for i,line in enumerate(LINES):
        story['scenes'][32+i]['text']=line
        story['scenes'][36+i]['text']=line
    story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
    return story


def fixed_response(schema,*args,**kwargs):
    return {key:dict(text=FIXED[int(key.split('_')[1])-36],
        visual='Arjun in his fixed yellow shirt studies the actual exam question at his desk while his father brings tea.') for key in schema['properties']}


class RepetitionRecovery(unittest.TestCase):
    def test_actual_echo_is_rejected_and_second_request_explains_why(self):
        story=production_echo_story();original=copy.deepcopy(story)
        prompts=[]
        def model(schema,prompt,*args,**kwargs):
            prompts.append(prompt)
            if len(prompts)==1:
                return {key:dict(text=story['scenes'][int(key.split('_')[1])]['text'],visual=story['scenes'][36]['visual']) for key in schema['properties']}
            return fixed_response(schema)
        with tempfile.TemporaryDirectory() as folder,patch('story_plan.ask',side_effect=model):
            repair_repetition(Path(folder),story)
            self.assertEqual(repeated_scenes(story['scenes']),[])
            self.assertIn('unchanged_echo',prompts[1])
            self.assertIn(LINES[0],prompts[0])
            self.assertEqual(story['scenes'][:36],original['scenes'][:36])
            self.assertEqual(story['scenes'][39:],original['scenes'][39:])
            self.assertEqual(len(prompts),3)
            # Both reconstructing the editorial source and repeating with the
            # accepted output reuse the exact saved prose, without inference.
            with patch('story_plan.ask') as inference:
                fresh=copy.deepcopy(original);repair_repetition(Path(folder),fresh)
                repair_repetition(Path(folder),story)
                inference.assert_not_called()
                self.assertEqual(fresh['scenes'],story['scenes'])

    def test_partial_success_survives_failure_and_resume_requests_only_pending(self):
        story=production_echo_story();original=copy.deepcopy(story)
        def partially_valid(schema,*args,**kwargs):
            result=fixed_response(schema)
            if 'scene_37' in result:result['scene_37']['text']=LINES[1]
            return result
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('story_plan.ask',side_effect=partially_valid),self.assertRaises(StoryValidationError) as error:
                repair_repetition(root,story)
            self.assertEqual(error.exception.details['pending_scenes'],[37])
            self.assertEqual(error.exception.details['rejections'],{'37':'unchanged_echo'})
            repaired=copy.deepcopy(story['scenes'])
            with patch('story_plan.ask',side_effect=fixed_response) as inference:
                restored=copy.deepcopy(original);repair_repetition(root,restored)
                self.assertEqual(set(inference.call_args.args[0]['properties']),{'scene_37'})
                self.assertEqual(restored['scenes'][36],repaired[36])
                self.assertEqual(restored['scenes'][38],repaired[38])
            different=copy.deepcopy(original);different['run_id']='other-story'
            with self.assertRaisesRegex(StoryValidationError,'identity_mismatch'):repair_repetition(root,different)

    def test_near_duplicate_and_new_echo_cannot_be_saved_as_a_repair(self):
        story=production_echo_story()
        def bad(schema,*args,**kwargs):
            return {key:dict(text=story['scenes'][0]['text'],visual=story['scenes'][0]['visual']) for key in schema['properties']}
        with tempfile.TemporaryDirectory() as folder,patch('story_plan.ask',side_effect=bad),self.assertRaises(StoryValidationError) as error:
            repair_repetition(Path(folder),story)
        self.assertEqual(error.exception.details['pending_scenes'],[36,37,38])
        self.assertTrue(all(value=='still_repeated_or_new_echo' for value in error.exception.details['rejections'].values()))

    def test_visual_batches_include_final_neighbors_without_distant_scene_payload(self):
        story=short_story();story.pop('visuals');story.pop('thumbnail_prompt');story.pop('thumbnail_scene')
        story['scenes'][40]['visual']='DISTANT_VISUAL_PAYLOAD_SHOULD_NOT_APPEAR'
        prompts=[]
        def model(schema,prompt,*args,**kwargs):
            prompts.append(prompt)
            if 'scene' in schema['properties']:
                return dict(scene=30,visual=record_for(story['scenes'][30],'Ram in his fixed blue kurta holds the story letter in his actual village shop before making his decision.'),viewer_question='What will Ram decide after reading the letter?')
            return {key:record_for(story['scenes'][int(key.split('_')[1])],'Ram in his fixed blue kurta handles the actual story parcel inside his village shop.') for key in schema['properties']}
        with tempfile.TemporaryDirectory() as folder,patch('story_plan.ask',side_effect=model):prepare_visuals(Path(folder),story)
        self.assertIn(story['scenes'][0]['text'],prompts[0])
        self.assertIn(story['scenes'][8]['text'],prompts[0])
        self.assertNotIn(story['scenes'][40]['text'],prompts[0])
        self.assertNotIn('DISTANT_VISUAL_PAYLOAD_SHOULD_NOT_APPEAR',''.join(prompts))
