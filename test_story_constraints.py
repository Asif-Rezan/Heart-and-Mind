"""Regression for real sample failures: decoder word caps and stale artifact merges."""
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch,Mock
import yaml
from story_constraints import hindi_word_pattern,is_hindi_word_pattern,edit_word_limits,hindi_cta_pattern,is_hindi_cta_pattern
from story_restore import restore_artifacts
from story_writer import save_json,object_schema,string
import test_lyrics_cpu
from test_pipeline_sample import sample_story
import lyrics_cpu


class HindiWordBounds(unittest.TestCase):
    def test_small_hindi_grammar_rejects_overlong_english_and_multispace_text(self):
        pattern=hindi_word_pattern(4,8)
        self.assertTrue(is_hindi_word_pattern(pattern))
        self.assertTrue(re.fullmatch(pattern,'पिता ने अपनी पुरानी किताब खोली।'))
        for text in ('पिता ने किताब खोली और फिर पूरी रात उसे पढ़ते रहे।','This is English text.', 'पिता  ने किताब खोली।'):
            self.assertIsNone(re.fullmatch(pattern,text))
        self.assertFalse(is_hindi_word_pattern(hindi_word_pattern(4,8).replace('{3,7}','{3,1000}')))
        with self.assertRaises(ValueError):hindi_word_pattern(4,1000)

    def test_closing_grammar_requires_viewer_question_and_comment_within_budget(self):
        pattern=hindi_cta_pattern(4,15)
        self.assertTrue(is_hindi_cta_pattern(pattern))
        valid='आप इन बच्चों की जगह होते तो क्या करते? टिप्पणी में बताइए।'
        self.assertTrue(re.fullmatch(pattern,valid))
        # Exact duplicate returned on both attempts by production job 124876475704.
        rejected='बच्चे साथ में उठकर नए लक्ष्यों की ओर देखते हैं, नोटबुक उनके हाथ में हैं।'
        for text in (rejected,'आप इन बच्चों की जगह होते तो क्या करते?',valid+' अभी',valid.replace('क्या करते','क्या करते और फिर आगे क्या करते और किससे मदद लेते')):
            self.assertIsNone(re.fullmatch(pattern,text))
        self.assertFalse(is_hindi_cta_pattern(pattern.replace('{0,10}','{0,1000}')))
        with self.assertRaises(ValueError):hindi_cta_pattern(4,4)

    def test_native_decoder_retains_closing_requirement_on_every_retry(self):
        helper=test_lyrics_cpu.QwenTests();payload=helper.payload()
        pattern=hindi_cta_pattern(4,15)
        payload['response_format']['json_schema']['schema']=object_schema({'text':dict(string(20,400),pattern=pattern)})
        bad=helper.result(json.dumps({'text':'बच्चे साथ में उठकर नए लक्ष्यों की ओर देखते हैं, नोटबुक उनके हाथ में हैं।'}))
        good=helper.result(json.dumps({'text':'आप इन बच्चों की जगह होते तो क्या करते? टिप्पणी में बताइए।'}))
        model=helper.model(create_chat_completion=Mock(side_effect=[bad,good]))
        with patch.object(lyrics_cpu,'load_model',return_value=model):
            lyrics_cpu.request_story('chat/completions',payload)
        for call in model.create_chat_completion.call_args_list:
            self.assertEqual(call.kwargs['response_format']['schema']['properties']['text']['pattern'],pattern)
        self.assertIn('end exactly with',model.create_chat_completion.call_args.kwargs['messages'][-1]['content'])

    def test_closing_schema_compiles_with_installed_native_cpu_runtime(self):
        try:
            from llama_cpp import LlamaGrammar
        except ImportError:
            self.skipTest('Native runtime is checked in the production outline job')
        schema=object_schema({'scene_47':object_schema({
            'text':dict(type='string',pattern=hindi_cta_pattern(4,15)),
            'visual':{'type':'string'}})})
        self.assertIsNotNone(LlamaGrammar.from_json_schema(json.dumps(schema),verbose=False))

    def test_shared_growth_is_allocated_once_for_the_whole_edit_batch(self):
        story=sample_story()
        total=sum(len(s['text'].split()) for s in story['scenes'])
        story['scenes'][0]['text']+=' '+' '.join(['सुबह']*(161-total))
        limits=edit_word_limits(story,[4,6])
        words=sum(len(s['text'].split()) for s in story['scenes'])
        base=words-sum(v['current_words'] for v in limits.values())
        self.assertLessEqual(base+sum(v['maximum_words'] for v in limits.values()),165)
        self.assertGreaterEqual(base+sum(v['minimum_words'] for v in limits.values()),120)

    def test_native_decoder_keeps_only_whitelisted_small_word_pattern(self):
        helper=test_lyrics_cpu.QwenTests();payload=helper.payload()
        payload['response_format']['json_schema']['schema']=object_schema({
            'text':dict(string(1,400),pattern=hindi_word_pattern(4,8)),
            'other':dict(string(1,1000),pattern='^.{1,1000}$')})
        result=helper.result(json.dumps(dict(text='पिता ने अपनी पुरानी किताब खोली।',other='safe')))
        model=helper.model(create_chat_completion=Mock(return_value=result))
        with patch.object(lyrics_cpu,'load_model',return_value=model):lyrics_cpu.request_story('chat/completions',payload)
        properties=model.create_chat_completion.call_args.kwargs['response_format']['schema']['properties']
        self.assertEqual(properties['text'],dict(type='string',pattern=hindi_word_pattern(4,8)))
        self.assertEqual(properties['other'],dict(type='string'))


class DeterministicArtifactRestore(unittest.TestCase):
    def test_latest_prose_preserves_repaired_chapters_and_review_in_any_download_order(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder);source=base/'download';run='sample-test'
            # Create newest first, simulating arbitrary parallel download completion.
            for stage,text in [('prose','corrected'),('chapter','original'),('outline','original')]:
                root=source/f'story-{stage}-123'/run
                save_json(root/'chapters/chapter-0.json',dict(text=text))
                save_json(root/'story-draft.json',dict(run_id=run))
            save_json(source/'story-prose-123'/run/'engagement-review.json',dict(identity='matching-corrected-prose',complete=['2']))
            restore_artifacts(source,base/'output',run)
            root=base/'output'/run
            self.assertEqual(json.loads((root/'chapters/chapter-0.json').read_text())['text'],'corrected')
            self.assertEqual(json.loads((root/'engagement-review.json').read_text())['complete'],['2'])
            self.assertFalse((base/'output'/'other-story').exists())

    def test_wrong_story_is_not_restored(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);save_json(root/'source/story-prose-123/wanted/story-draft.json',dict(run_id='different'))
            with self.assertRaisesRegex(ValueError,'identity mismatch'):restore_artifacts(root/'source',root/'out','wanted')

    def test_workflows_restore_separately_and_workers_upload_only_their_owned_result(self):
        for filename in ('stories.yml','story-plan-preview.yml'):
            jobs=yaml.safe_load((Path('.github/workflows')/filename).read_text())['jobs']
            entry=jobs.get('outline',jobs['prose'])
            steps=entry['steps']
            restore=next(s for s in steps if s.get('uses')=='actions/download-artifact@v4' and 'run-id' in s.get('with',{}))
            self.assertIs(restore['with']['merge-multiple'],False)
            self.assertTrue(any('story_restore.py' in s.get('run','') for s in steps))
            for job in ('planning_seo','planning_thumbnail','planning_visuals'):
                upload=next(s for s in jobs[job]['steps'] if s.get('uses')=='actions/upload-artifact@v4')
                self.assertNotIn('planning-*.json',upload['with']['path'])
