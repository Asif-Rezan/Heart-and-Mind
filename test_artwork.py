from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops
from artwork import create_artwork, vintage_finish, vintage_thumbnail
from demo_artwork import SONG


class VintageArtworkTests(unittest.TestCase):
    def test_vintage_finish_is_reproducible_and_monochrome(self):
        source = Image.new('RGB', (320, 180), '#8d5340')
        first = vintage_finish(source)
        second = vintage_finish(source)
        self.assertIsNone(ImageChops.difference(first, second).getbbox())
        red, green, blue = first.split()
        self.assertIsNone(ImageChops.difference(red, green).getbbox())
        self.assertIsNone(ImageChops.difference(red, blue).getbbox())

    def test_full_artwork_keeps_export_sizes_and_colorless_style(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for kind in ('background', 'thumbnail'):
                Image.new('RGB', (1024, 576), '#5678a0').save(root/f'{kind}-source.png')
            create_artwork(root, SONG)
            for name, size in (('cover.png', (1920, 1080)), ('thumbnail.jpg', (1280, 720))):
                with Image.open(root/name) as output:
                    self.assertEqual(output.size, size)
                    red, green, blue = output.convert('RGB').split()
                    self.assertIsNone(ImageChops.difference(red, green).getbbox())
                    self.assertIsNone(ImageChops.difference(red, blue).getbbox())

    def test_title_panel_does_not_extend_over_left_portrait(self):
        source = Image.new('RGB', (1280, 720), 'white')
        output = vintage_thumbnail(source, SONG, 'romance')
        self.assertGreater(output.getpixel((400, 400))[0], 230)
        self.assertLess(output.getpixel((1000, 430))[0], 35)

    def test_whole_source_remains_visible_in_portrait_panel(self):
        source = Image.new('RGB', (1024, 576), '#ffffff')
        source.paste(Image.new('RGB', (512, 576), '#888888'), (512, 0))
        output = vintage_thumbnail(source, SONG, 'romance')
        self.assertGreater(output.getpixel((100, 400))[0], 230)
        self.assertTrue(70 < output.getpixel((600, 400))[0] < 180)
