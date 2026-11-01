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

    def test_editor_repairs_only_flagged_slot_then_rechecks_and_resumes(self):
        story=short_story();original=copy.deepcopy(story['scenes'])
        bad=dict(hook=False,progression=True,payoff=True,cta=True,repairs=[dict(scene=0,instruction='Open with the actual unresolved story dilemma.')])
        good=dict(hook=True,progression=True,payoff=True,cta=True,repairs=[])
        revised='आज दुकान बंद होने से पहले राम को एक कठिन फैसला करना था।'
        response={'scene_0':dict(text=revised,visual='Ram in his blue kurta stands at the door of his village shop, holding a letter.')}
        with tempfile.TemporaryDirectory() as folder,patch('story_engagement.ask',side_effect=[bad,response,good]) as model:
            polish_engagement(Path(folder),story)
            self.assertEqual(model.call_count,3)
            self.assertEqual(story['scenes'][0]['text'],revised)
            self.assertEqual(story['scenes'][1:],original[1:])
            self.assertIn(revised,model.call_args.args[1])
            fresh=short_story();polish_engagement(Path(folder),fresh)
            self.assertEqual(model.call_count,3)
            self.assertEqual(fresh['scenes'],story['scenes'])
            self.assertTrue(json.loads((Path(folder)/'engagement-review.json').read_text())['approved'])

    def test_failed_editor_review_stops_instead_of_claiming_engagement(self):
        failed=dict(hook=False,progression=False,payoff=False,cta=False,repairs=[])
        with tempfile.TemporaryDirectory() as folder,patch('story_engagement.ask',return_value=failed),self.assertRaisesRegex(ValueError,'did not pass'):
            polish_engagement(Path(folder),short_story())

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
