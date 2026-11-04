import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

from couple_background import (background_plan, checked_cutout, compose_background,
                               generate_background, generate_background_part)
from song_images import image_plan, generate_song_images

SONG = dict(title='तेरे साथ', lyrics='तेरे साथ चाँदनी', visual_mood='romance',
            background_setting='moonlit bookshop, amber lantern')


class CoupleBackgroundTests(unittest.TestCase):
    def test_casting_is_isolated_and_thumbnail_is_unchanged(self):
        background, thumbnail = image_plan(SONG)
        parts = {part['role']: part for part in background['parts']}
        self.assertEqual(set(parts), {'scenery', 'man', 'woman'})
        self.assertNotIn('woman', parts['man']['prompt'])
        self.assertNotIn(' man ', parts['woman']['prompt'])
        self.assertIn('Empty unoccupied setting', parts['scenery']['prompt'])
        self.assertIn('moonlit bookshop', parts['scenery']['prompt'])
        self.assertIn('people', parts['scenery']['extra_negative'])
        self.assertEqual(len({p['seed'] for p in parts.values()}), 3)
        self.assertNotIn('parts', thumbnail)
        self.assertTrue(thumbnail['allow_text'])
        self.assertEqual(thumbnail, image_plan(dict(SONG, background_setting='garden'))[1])

    def test_portraits_cannot_overlap_or_cover_left_overlay_space(self):
        scenery = Image.new('RGB', (1000, 600), 'navy')
        man = Image.new('RGBA', (600, 600), 'red')
        woman = Image.new('RGBA', (600, 600), 'lime')
        result = compose_background(scenery, man, woman, (1000, 600))
        self.assertEqual(result.getpixel((520, 500)), (255, 0, 0))
        self.assertEqual(result.getpixel((800, 500)), (0, 255, 0))
        for x in (0, 350, 660, 680, 690, 980):
            self.assertEqual(result.getpixel((x, 500)), (0, 0, 128))

    def test_cutout_rejects_empty_or_unremoved_background(self):
        rembg = types.SimpleNamespace(remove=Mock())
        with patch.dict('sys.modules', {'rembg': rembg}):
            for color in ((0, 0, 0, 0), (0, 0, 0, 255)):
                rembg.remove.return_value = Image.new('RGBA', (100, 100), color)
                with self.assertRaises(ValueError):
                    checked_cutout(Image.new('RGB', (100, 100)), object())

    def test_interrupted_generation_resumes_completed_parts(self):
        plan = image_plan(SONG)[0]
        def generate(prompt, target, **kwargs):
            if 'woman' in prompt:
                raise RuntimeError('interrupted')
            Image.new('RGB', (64, 64), 'navy').save(target)
        with tempfile.TemporaryDirectory() as folder, patch('image_cpu.generate', side_effect=generate) as worker:
            with self.assertRaises(RuntimeError):
                generate_background(folder, plan, Path(folder)/'background-source.png')
            self.assertEqual(worker.call_count, 3)
            self.assertFalse((Path(folder)/'background-source.png').exists())
            self.assertTrue((Path(folder)/'background-man.json').exists())
            worker.reset_mock()
            for role in ('scenery', 'man'):
                generate_background_part(folder, plan, role)
            worker.assert_not_called()
            changed = background_plan(dict(SONG, background_setting='garden'), plan)
            generate_background_part(folder, changed, 'man')
            worker.assert_not_called()
            generate_background_part(folder, changed, 'scenery')
            self.assertEqual(worker.call_count, 1)

    def test_layered_background_flows_through_production_checkpoint(self):
        def generate(prompt, target, **kwargs):
            Image.new('RGB', (100, 100), 'navy').save(target)
        def remove(image, **kwargs):
            result = Image.new('RGBA', image.size)
            ImageDraw.Draw(result).rectangle((25, 10, 75, 99), fill='red')
            return result
        rembg = types.SimpleNamespace(new_session=Mock(), remove=remove)
        with tempfile.TemporaryDirectory() as folder, patch.dict('sys.modules', {'rembg': rembg}), patch('image_cpu.generate', side_effect=generate) as worker:
            generate_song_images(folder, SONG)
            self.assertEqual(worker.call_count, 4)
            with Image.open(Path(folder)/'background-source.png') as image:
                self.assertEqual(image.size, (1024, 576))
            manifest = json.loads((Path(folder)/'image-manifest.json').read_text())
            self.assertEqual(manifest['background']['composition'], 'separate-portraits')
            generate_song_images(folder, SONG)
            self.assertEqual(worker.call_count, 4)
            with patch('couple_background.checked_cutout', side_effect=ValueError('bad mask')):
                with self.assertRaises(ValueError):
                    generate_song_images(folder, dict(SONG, background_setting='different garden'))
            self.assertEqual(json.loads((Path(folder)/'image-manifest.json').read_text()), manifest)


if __name__ == '__main__':
    unittest.main()
