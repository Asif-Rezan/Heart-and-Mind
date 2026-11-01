"""Editorial acceptance/repair and audible, correctly placed short-story score sections."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from story_engagement import chapter_direction,polish_engagement
from daily_story import score_request,mix_score
from story_writer import save_json,text_hash
from test_short_story import short_story,timeline


class EngagementTests(unittest.TestCase):
    def test_hooks_and_cta_are_assigned_to_correct_chapters(self):
        self.assertIn('first two',chapter_direction(0))
        self.assertIn('AFTER',chapter_direction(5))
        self.assertIn('comment',chapter_direction(5))
        self.assertIn('resistance',chapter_direction(4))

    def test_editor_repairs_only_frozen_slot_without_a_second_subjective_audit(self):
        story=short_story();original=copy.deepcopy(story['scenes'])
        review=dict(hook=False,progression=True,payoff=True,cta=True,repairs=[dict(scene=0,instruction='Open with the actual unresolved story dilemma.')])
        revised='आज दुकान बंद होने से पहले राम को एक कठिन फैसला करना था।'
        response={'scene_0':dict(text=revised,visual='Ram in his blue kurta stands at the door of his village shop, holding a letter.')}
        with tempfile.TemporaryDirectory() as folder,patch('story_engagement.ask',side_effect=[review,response]) as model:
            polish_engagement(Path(folder),story)
            self.assertEqual(model.call_count,2)
            self.assertEqual(story['scenes'][0]['text'],revised)
            self.assertEqual(story['scenes'][1:],original[1:])
            self.assertIn('frozen',model.call_args.args[1])
            fresh=short_story();polish_engagement(Path(folder),fresh)
            self.assertEqual(model.call_count,2)
            self.assertEqual(fresh['scenes'],story['scenes'])
            saved=json.loads((Path(folder)/'engagement-review.json').read_text())
            self.assertTrue(saved['approved'])
            self.assertEqual(saved['approval_basis'],'fixed_plan_edits_validated')

    def test_changed_upstream_prose_reaudits_without_applying_stale_edits(self):
        story=short_story();original=copy.deepcopy(story['scenes'])
        review=dict(hook=True,progression=True,payoff=True,cta=True,repairs=[])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            save_json(root/'engagement-review.json',dict(identity='old-source',scenes=[],review={},complete=[]))
            with patch('story_engagement.ask',return_value=review) as model:
                polish_engagement(root,story)
            model.assert_called_once()
            self.assertEqual(story['scenes'],original)
            self.assertTrue((root/'engagement-review-stale-old-source.json').exists())
            self.assertNotEqual(json.loads((root/'engagement-review.json').read_text())['identity'],'old-source')

    def test_incomplete_progression_plan_reports_specific_safe_error(self):
        failed=dict(hook=False,progression=False,payoff=False,cta=False,repairs=[])
        with tempfile.TemporaryDirectory() as folder,patch('story_engagement.ask',return_value=failed),self.assertRaisesRegex(ValueError,'editorial_plan_incomplete'):
            polish_engagement(Path(folder),short_story())

    def test_actual_failed_audit_shape_resumes_saved_prose_without_reauditing(self):
        from story_engagement import has_closing_cta
        story=short_story();identity=__import__('hashlib').sha256(json.dumps(story['scenes'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        # Same all-false final judgement and exact target indices as failed run 41285860535.
        review=dict(hook=False,progression=False,payoff=False,cta=False,
            repairs=[dict(scene=i,instruction='Repair this causal beat using only the established character and canonical event.') for i in (0,1,2,3,14,36)])
        saved_scenes=copy.deepcopy(story['scenes']);saved_scenes[10]['text']='उस सुबह उसने पुरानी किताब खोली और अपना अधूरा काम पूरा किया।'
        calls=[]
        def edit(schema,*args,**kwargs):
            calls.append(schema)
            self.assertTrue(all(key.startswith('scene_') for key in schema['properties']))
            result={}
            for key in schema['properties']:
                i=int(key.split('_')[1]);text='आज '+story['scenes'][i]['text']
                if i==47:text='आप इस परिवार के फैसले पर क्या सोचते हैं, टिप्पणी लिखकर हमें बताइए।'
                result[key]=dict(text=text,visual='Ram in his fixed blue kurta holds the story letter inside his small village shop.')
            return result
        with tempfile.TemporaryDirectory() as folder,patch('story_engagement.ask',side_effect=edit):
            root=Path(folder);save_json(root/'engagement-review.json',dict(identity=identity,scenes=saved_scenes,review=review,approved=False))
            polish_engagement(root,story)
            self.assertEqual(story['scenes'][10],saved_scenes[10])
            self.assertEqual(len(calls),4)
            self.assertTrue(has_closing_cta(story['scenes']))
            self.assertEqual(len(json.loads((root/'engagement-review.json').read_text())['complete']),8)

    def test_invalid_edit_checkpoints_accepted_slots_and_resume_only_missing(self):
        story=short_story();review=dict(hook=False,progression=True,payoff=True,cta=True,
            repairs=[dict(scene=0,instruction='Open with a concrete dilemma.'),dict(scene=1,instruction='Clarify the uncertain consequence.')])
        valid=dict(text='आज राम ने दुकान के दरवाजे पर एक अनजानी चिट्ठी देखी।',visual='Ram in a blue kurta sees a letter at the door of his small village shop.')
        bad={'scene_0':valid,'scene_1':dict(text='invalid English',visual=valid['visual'])}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch('story_engagement.ask',side_effect=[review,bad,{'scene_1':bad['scene_1']}]),self.assertRaisesRegex(ValueError,'editorial_edit_incomplete'):
                polish_engagement(root,story)
            saved=json.loads((root/'engagement-review.json').read_text())
            self.assertEqual(saved['complete'],['0'])
            fresh=short_story()
            fixed={'scene_1':dict(text='वह चिट्ठी खोलने से डर रहा था क्योंकि उसमें उसके पिता का नाम था।',visual=valid['visual'])}
            with patch('story_engagement.ask',return_value=fixed) as model:
                polish_engagement(root,fresh)
                self.assertEqual(set(model.call_args.args[0]['properties']),{'scene_1'})
                self.assertEqual(fresh['scenes'][0]['text'],valid['text'])
                model.assert_called_once()

    def test_score_has_intro_tension_and_final_payoff_with_shared_musical_direction(self):
        story=short_story()
        requests=[score_request(story,i) for i in range(3)]
        for request in requests:
            self.assertTrue(request['instrumental'])
            self.assertEqual(request['duration'],120)
            self.assertIn('78 BPM',request['prompt'])
            self.assertIn(story['summary'],request['prompt'])
            self.assertIn('no vocals',request['prompt'])
        self.assertIn('curiosity',requests[0]['prompt'])
        self.assertIn('turning point',requests[1]['prompt'])
        self.assertIn('hopeful emotional payoff',requests[2]['prompt'])
        with self.assertRaises(ValueError):score_request(story,3)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'FFmpeg required')
class ShortMusicSmoke(unittest.TestCase):
    def test_three_sections_cover_entire_four_minute_arc_at_consistent_level(self):
        import numpy as np
        import wave
        def read_audio(path):
            with wave.open(str(path),'rb') as audio:
                return np.frombuffer(audio.readframes(audio.getnframes()),dtype='<i2').astype(float)/32768,audio.getframerate()
        from story_media import digest
        from pipeline import duration
        story=short_story();timing=timeline(240)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=440:sample_rate=24000:duration=240',str(root/'narration.wav')],check=True)
            original=digest(root/'narration.wav')
            for i,(hz,amplitude) in enumerate(((150,.3),(250,1),(350,2))):
                part=root/'score'/f'part-{i}';part.mkdir(parents=True)
                subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'sine=frequency={hz}:sample_rate=24000:duration=120','-af',f'volume={amplitude}',str(part/'bgm.wav')],check=True)
                save_json(part/'request.json',dict(story_hash=text_hash(story['lyrics']),run_id=story['run_id'],request=score_request(story,i),index=i))
            mix_score(root,story,timing)
            self.assertEqual(original,digest(root/'narration.wav'))
            self.assertAlmostEqual(duration(root/'song.wav'),240,places=2)
            self.assertAlmostEqual(duration(root/'background.wav'),240,places=2)
            audio,rate=read_audio(root/'background.wav')
            energies=[]
            for second,hz in ((20,150),(100,250),(200,350)):
                sample=audio[second*rate:(second+1)*rate]
                spectrum=np.abs(np.fft.rfft(sample))
                frequency=np.fft.rfftfreq(len(sample),1/rate)[spectrum.argmax()]
                self.assertAlmostEqual(frequency,hz,delta=2)
                energies.append(np.sqrt(np.mean(sample**2)))
            self.assertLess(max(energies)/min(energies),1.1)
            mixed,_=read_audio(root/'song.wav')
            self.assertLessEqual(np.max(np.abs(mixed)),.96)
            self.assertEqual(json.loads((root/'mix.json').read_text())['section_seconds'],80)
