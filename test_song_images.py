import datetime as dt
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch, Mock
from PIL import Image

import image_cpu
from song_images import image_plan, generate_song_images
from pipeline import metadata_tags, song_profile, SONG_PROFILES

SONG = dict(title='नई सुबह', lyrics='नई सुबह में फिर से जीना है', prompt='Hopeful Hindi folk pop',
            visual_mood='healing', tags=['Hindi Folk Song', 'hindi folk song', 'नई सुबह'])


class SongImageTests(unittest.TestCase):
    def test_distinct_purpose_and_song_seeds(self):
        first = image_plan(SONG)
        second = image_plan(dict(SONG, lyrics='तेरे साथ चलना है'))
        self.assertNotEqual(first[0]['seed'], first[1]['seed'])
        self.assertNotEqual(first[0]['seed'], second[0]['seed'])
        self.assertNotEqual(first[0]['prompt'], first[1]['prompt'])
        self.assertEqual(first, image_plan(SONG))
        self.assertTrue(all(item['revision'] == image_cpu.REVISION for item in first))

    def test_framing_survives_long_scene_prompts_and_purposes_stay_distinct(self):
        long_scene = 'Adult South Asian couple sharing a quiet reunion under a courtyard lamp ' + 'long scenery description ' * 60
        plans = image_plan(dict(SONG, background_prompt=long_scene, thumbnail_prompt=long_scene))
        self.assertTrue(plans[0]['prompt'].startswith('Medium-wide'))
        self.assertTrue(plans[1]['prompt'].startswith('Chest-up'))
        self.assertIn('large expressive faces', plans[1]['prompt'])
        self.assertIn('dark empty left', plans[1]['prompt'])
        for plan in plans:
            self.assertLessEqual(len(plan['prompt'].split()), 62)
            self.assertIn('courtyard lamp', plan['prompt'])
            self.assertIn('fully clothed adults', plan['prompt'])
            self.assertNotIn('Hopeful Hindi folk pop', plan['prompt'])

    def test_checkpoint_reuses_only_matching_song_and_prompt(self):
        def generate(prompt, target, seed):
            Image.new('RGB', (256, 256), 'navy').save(target)
        with tempfile.TemporaryDirectory() as temp, patch('image_cpu.generate', side_effect=generate) as worker:
            root = Path(temp)
            generate_song_images(root, SONG)
            self.assertEqual(worker.call_count, 2)
            generate_song_images(root, SONG)
            self.assertEqual(worker.call_count, 2)
            generate_song_images(root, dict(SONG, thumbnail_prompt='New scene of a hopeful adult watching the sunrise'))
            self.assertEqual(worker.call_count, 3)
            generate_song_images(root, dict(SONG, lyrics='एक नया गीत'))
            self.assertEqual(worker.call_count, 5)

    def test_partial_failure_keeps_first_image_for_retry(self):
        def generate(prompt, target, seed):
            if 'thumbnail' in str(target):
                raise RuntimeError('interrupted')
            Image.new('RGB', (256, 256), 'navy').save(target)
        with tempfile.TemporaryDirectory() as temp, patch('image_cpu.generate', side_effect=generate):
            with self.assertRaises(RuntimeError):
                generate_song_images(Path(temp), SONG)
            manifest = json.loads((Path(temp)/'image-manifest.json').read_text())
            self.assertIn('background', manifest)
            self.assertNotIn('thumbnail', manifest)

    def test_safety_rejected_output_is_never_saved(self):
        worker = Mock(return_value=types.SimpleNamespace(nsfw_content_detected=[True], images=[Image.new('RGB', (256, 256))]))
        torch = types.SimpleNamespace(set_num_threads=Mock(), Generator=Mock())
        diffusers = types.SimpleNamespace(DiffusionPipeline=Mock(), DPMSolverMultistepScheduler=Mock())
        with tempfile.TemporaryDirectory() as temp, patch.object(image_cpu, '_pipeline', worker), patch.dict('sys.modules', {'torch': torch, 'diffusers': diffusers}):
            path = Path(temp)/'scene.png'
            with self.assertRaises(image_cpu.ImageSafetyBlocked):
                image_cpu.generate('Adult couple walking in a park', path, seed=123)
            self.assertEqual(worker.call_count, 10)
            self.assertFalse(path.exists())

    def test_metadata_tags_are_unique_and_fit_upload_limit(self):
        tags = metadata_tags(SONG)
        self.assertEqual(len([t for t in tags if t.lower() == 'hindi folk song']), 1)
        tags = metadata_tags(dict(SONG, tags=['a'*38 + str(i) for i in range(30)]))
        self.assertLessEqual(sum(len(t) + (2 if ' ' in t else 0) + 1 for t in tags), 480)

    def test_daily_rotation_covers_all_song_styles_without_history_access(self):
        start = dt.date(2026, 10, 26)
        profiles = [song_profile((start + dt.timedelta(days=i)).isoformat()) for i in range(8)]
        self.assertEqual(set(profiles), set(SONG_PROFILES))


if __name__ == '__main__':
    unittest.main()
