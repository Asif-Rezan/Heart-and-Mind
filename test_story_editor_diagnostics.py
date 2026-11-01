"""Production maxLength retry, wrong planning language, and actionable editorial failures."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from jsonschema import Draft202012Validator,ValidationError
from story_writer import ask,object_schema,string,OUTLINE
from test_story_parallel import outline_fixture


class EditorialMetadataRegression(unittest.TestCase):
    def test_overlong_repair_instructions_bound_without_second_model_generation(self):
        schema=object_schema({'repairs':{'type':'array','items':object_schema({'instruction':string(10,240)})}})
        raw=dict(repairs=[dict(instruction='Repair this causal transition without inventing a new character. '*10)])
        def inference(endpoint,payload):
            # The real CPU layer validates before ask can normalize metadata.
            Draft202012Validator(payload['response_format']['json_schema']['schema']).validate(raw)
            return {'choices':[{'message':{'content':json.dumps(raw)}}]}
        with tempfile.TemporaryDirectory() as folder,patch('lyrics_cpu.request_story',side_effect=inference) as model:
            path=Path(folder)/'editor-audit.json'
            result=ask(schema,'Audit',123,checkpoint=path)
            self.assertLessEqual(len(result['repairs'][0]['instruction']),240)
            self.assertEqual(json.loads(path.read_text()),raw)
            model.assert_called_once()

    def test_overlong_thumbnail_from_failed_recovery_is_bounded_without_retry(self):
        schema=object_schema({'scene':{'type':'integer','minimum':0,'maximum':47},'thumbnail_prompt':string(80,360)})
        raw=dict(scene=31,thumbnail_prompt='Arjun in his yellow shirt holds the actual story notebook beside his father in a blue kurta, warm expressive faces. '*6)
        def inference(endpoint,payload):
            Draft202012Validator(payload['response_format']['json_schema']['schema']).validate(raw)
            return {'choices':[{'message':{'content':json.dumps(raw)}}]}
        with tempfile.TemporaryDirectory() as folder,patch('lyrics_cpu.request_story',side_effect=inference) as model:
            result=ask(schema,'Select actual story thumbnail',123,checkpoint=Path(folder)/'thumbnail-selection.json')
            self.assertEqual(result['scene'],31)
            self.assertTrue(80<=len(result['thumbnail_prompt'])<=360)
            self.assertTrue(raw['thumbnail_prompt'].startswith(result['thumbnail_prompt']))
            model.assert_called_once()

    def test_hindi_planning_from_failed_production_shape_is_rejected_before_chapters(self):
        outline=outline_fixture()
        outline['characters']='माँ राजेश्वरी और उसके परिवार की कहानी। '*5
        with self.assertRaises(ValidationError):Draft202012Validator(OUTLINE).validate(outline)
        outline=outline_fixture()
        Draft202012Validator(OUTLINE).validate(outline)
        self.assertIn('एक नई शुरुआत',outline['title'])
