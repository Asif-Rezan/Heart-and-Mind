"""Shared thumbnail generation and 16:9 delivery dimensions."""
from pathlib import Path
from PIL import Image, ImageOps

SOURCE_SIZE = (1344, 768)
EXPORT_SIZE = (1920, 1080)


def export_thumbnail(source, target):
    """Center crop to 16:9, then resize with Lanczos (1344x768 loses 6px per edge)."""
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        output = ImageOps.fit(image.convert('RGB'), EXPORT_SIZE,
                              method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        output.save(target, format='JPEG', quality=92, optimize=True)
