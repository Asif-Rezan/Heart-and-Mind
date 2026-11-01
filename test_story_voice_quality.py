"""Voice identity, safe model loading, pause shaping and silent-output guards."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from story_voice_model import voice_profile,GOONJ_REVISION
from story_voice import prepare_speech,scene_pause,voice_identity,SAMPLE_RATE,next_native_speed
from test_short_story import short_story


class VoiceQualityChecks(unittest.TestCase):
    def test_user_selected_kokoro_is_the_default(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(voice_profile()['engine'],'kokoro')
            self.assertEqual(voice_profile()['voice'],'hm_omega')

    def test_native_rate_adjustments_are_modest_and_do_not_force_five_minutes(self):
        story=short_story()
        self.assertEqual(next_native_speed(story,1.0,270),1.0)
        self.assertEqual(next_native_speed(story,1.0,230),.92)
        self.assertEqual(next_native_speed(story,1.0,150),.90)
        self.assertEqual(next_native_speed(story,1.0,500),1.08)

    def test_stock_voice_profiles_are_pinned_and_invalid_combinations_fail(self):
        profile=voice_profile('goonj','hi_ravi')
        self.assertEqual(profile['revision'],GOONJ_REVISION)
        self.assertEqual(profile['voice'],'hi_ravi')
        self.assertEqual(voice_profile(legacy=True)['voice'],'hm_omega')
        for engine,voice in [('goonj','hm_omega'),('kokoro','hi_ravi'),('unknown','hi_ravi')]:
            with self.assertRaises(ValueError):voice_profile(engine,voice)

    def test_voice_change_invalidates_cached_audio_identity(self):
        story=short_story()
        a=voice_identity(story,1.0,voice_profile('kokoro','hm_omega'))
        b=voice_identity(story,1.0,voice_profile('goonj','hi_ravi'))
        c=voice_identity(story,1.0,voice_profile('goonj','hi_atul'))
        self.assertEqual(len({a,b,c}),3)

    def test_silence_trim_preserves_quiet_consonants_and_only_shortens_edges(self):
        speech=np.full(SAMPLE_RATE,.01,dtype=np.float32)
        source=np.concatenate([np.zeros(SAMPLE_RATE),speech,np.zeros(SAMPLE_RATE)])
        result=prepare_speech(source)
        self.assertAlmostEqual(len(result)/SAMPLE_RATE,1.26,places=2)
        self.assertTrue(np.allclose(result[2400:26400],speech))
        for bad in (np.zeros(100),np.array([np.nan]),np.zeros((20,2))):
            with self.assertRaises(RuntimeError):prepare_speech(bad)

    def test_pauses_follow_chapters_and_do_not_append_silence_after_final_line(self):
        story=short_story()
        self.assertEqual(scene_pause(story,0),.08)
        self.assertEqual(scene_pause(story,7),.28)
        self.assertEqual(scene_pause(story,47),0)
        story['scenes'][1]['text']='आप क्या करेंगे?'
        self.assertEqual(scene_pause(story,1),.12)
