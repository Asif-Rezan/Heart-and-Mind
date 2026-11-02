"""Verify the requested native thumbnail size and small centered 16:9 crop."""
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw
from story_thumbnail import export_thumbnail


class ThumbnailExportChecks(unittest.TestCase):
    def test_1344_by_768_loses_only_six_rows_per_edge_and_exports_full_hd(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = Image.new('RGB', (1344, 768), 'green')
            draw = ImageDraw.Draw(source)
            draw.rectangle((0, 0, 1343, 5), fill='red')
            draw.rectangle((0, 762, 1343, 767), fill='blue')
            draw.rectangle((600, 300, 743, 467), fill='white')
            source.save(root/'source.png')
            export_thumbnail(root/'source.png', root/'thumbnail.jpg')
            with Image.open(root/'thumbnail.jpg') as result:
                self.assertEqual(result.size, (1920, 1080))
                self.assertEqual(result.format, 'JPEG')
                for at in ((960, 0), (960, 1079)):
                    red, green, blue = result.getpixel(at)
                    self.assertGreater(green, red + 80)
                    self.assertGreater(green, blue + 80)
                self.assertTrue(all(value > 245 for value in result.getpixel((960, 540))))
