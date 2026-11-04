from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image

import image_cpu
from song_images import image_plan, generate_song_images
from demo_artwork import SONG


class StorybookImageTests(unittest.TestCase):
    def test_defaults_are_coherent_natural_3d_without_cutout_pipeline(self):
        song = dict(SONG)
        song.pop('visual_style')
        background, thumbnail = image_plan(song)
        for plan in (background, thumbnail):
            self.assertEqual(plan['style'], 'storybook3d')
            self.assertEqual(plan['composition'], 'single-scene')
            self.assertNotIn('parts', plan)
            self.assertFalse(plan['allow_text'])
            self.assertTrue(plan['prompt'].startswith('Natural 3D storybook illustration'))
            self.assertIn('man in an oatmeal kurta', plan['prompt'])
            self.assertIn('woman in a sage sari', plan['prompt'])
            self.assertNotIn('red sari', plan['prompt'])
            self.assertNotIn('red brush', plan['prompt'])
            self.assertIn('Soft daylight', plan['prompt'])
            self.assertIn('red color cast', plan['extra_negative'])
        self.assertNotEqual(background['prompt'], thumbnail['prompt'])
        self.assertNotEqual(background['seed'], thumbnail['seed'])

    def test_actual_inference_allows_3d_and_suppresses_red_cast(self):
        worker = Mock(return_value=types.SimpleNamespace(
            nsfw_content_detected=[False], images=[Image.new('RGB', (256, 256))]))
        torch = types.SimpleNamespace(set_num_threads=Mock(), Generator=Mock())
        diffusers = types.SimpleNamespace(DiffusionPipeline=Mock(), DPMSolverMultistepScheduler=Mock())
        with tempfile.TemporaryDirectory() as folder, patch.object(image_cpu, '_pipeline', worker), patch.dict('sys.modules', {'torch': torch, 'diffusers': diffusers}):
            generate_song_images(folder, SONG)
            self.assertEqual(worker.call_count, 2)
            for call in worker.call_args_list:
                negative = call.kwargs['negative_prompt']
                self.assertNotIn('3D render', negative)
                self.assertNotIn('CGI', negative)
                self.assertIn('red color cast', negative)
                self.assertIn('gouache', negative)
                self.assertEqual(call.kwargs['guidance_scale'], 6.0)
            generate_song_images(folder, SONG)
            self.assertEqual(worker.call_count, 2)
            generate_song_images(folder, dict(SONG, background_setting='rainy bookshop window'))
            self.assertEqual(worker.call_count, 3)
