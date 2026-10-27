"""Compose song-specific artwork from two freshly generated cinematic scenes.

The SSD-1B image job supplies a separate background and thumbnail source.
"""
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, features

ASSETS = Path(__file__).resolve().parent / 'assets' / 'artwork'
MOODS = {
    'romance': ('#ffdf96', 'HINDI LOVE SONG', 'TERE SAATH'),
    'heartbreak': ('#c4dcff', 'HINDI SAD SONG', 'ADHURI BAATEIN'),
    'healing': ('#ffe4a1', 'HINDI SOULFUL SONG', 'NAYI SUBAH'),
}


def visual_mood(song):
    if song.get('visual_mood') in MOODS:
        return song['visual_mood']
    # Backwards-compatible inference for older song.json artifacts.
    text = (song.get('prompt', '') + ' ' + song.get('title', '')).lower()
    if any(word in text for word in ('sad', 'heartbreak', 'longing', 'दर्द', 'अधूर')):
        return 'heartbreak'
    if any(word in text for word in ('hope', 'healing', 'uplifting', 'नई सुबह')):
        return 'healing'
    return 'romance'


def font(size):
    for path in (ASSETS/'Oswald.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                 '/Library/Fonts/Arial Bold.ttf', 'DejaVuSans-Bold.ttf'):
        try:
            face = ImageFont.truetype(str(path), size)
            if Path(path).name == 'Oswald.ttf':
                face.set_variation_by_axes([650])
            return face
        except OSError:
            pass
    raise RuntimeError('A scalable bold font is required for artwork')


def hook_text(song, mood):
    hook = song.get('thumbnail_text', '').strip().upper()
    if (not re.fullmatch(r'[A-Z0-9 !?]{3,26}', hook) or
            not 2 <= len(hook.split()) <= 4 or 'HEART' in hook or 'MIND' in hook):
        return MOODS[mood][2]
    return hook


def draw_hook(image, hook, accent):
    draw = ImageDraw.Draw(image)
    words = hook.split()
    # At most three large lines; keep the people on the right unobstructed.
    candidates = [[hook]]
    candidates += [[' '.join(words[:i]), ' '.join(words[i:])] for i in range(1, len(words))]
    if len(words) >= 3:
        candidates.append([' '.join(words[:-2]), words[-2], words[-1]])
    for size in range(112, 43, -2):
        face = font(size)
        fitting = [lines for lines in candidates if all(draw.textbbox((0, 0), line, font=face)[2] <= 570 for line in lines)]
        if fitting:
            lines = min(fitting, key=lambda lines: max(len(line) for line in lines) - min(len(line) for line in lines))
            break
    y = 275 - (len(lines)-1)*size//3
    for line in lines:
        draw.text((62, y), line, font=face, fill=accent, stroke_width=3, stroke_fill='#11151f')
        y += int(size*1.12)


def vintage_finish(image):
    """Reproducible silver-gelatin tones and a lightly worn photographic border."""
    import numpy as np
    gray = ImageEnhance.Contrast(ImageOps.grayscale(image)).enhance(1.16)
    rng = np.random.default_rng(1994)
    pixels = np.asarray(gray, dtype=np.float32)
    pixels = np.clip(pixels + rng.normal(0, 2.2, pixels.shape), 0, 255).astype('uint8')
    image = Image.fromarray(pixels).convert('RGB')
    draw = ImageDraw.Draw(image)
    width, height = image.size
    draw.rectangle((3, 3, width-4, height-4), outline='#d8d8d8', width=2)
    for _ in range(650):
        x, y = int(rng.integers(0, width)), int(rng.integers(0, height))
        edge = int(rng.integers(0, 4))
        if edge == 0: y = int(rng.integers(0, 9))
        elif edge == 1: y = height-1-int(rng.integers(0, 9))
        elif edge == 2: x = int(rng.integers(0, 9))
        else: x = width-1-int(rng.integers(0, 9))
        draw.line((x, y, min(width-1, x+int(rng.integers(1, 14))), y), fill='#dddddd', width=1)
    return image


def vintage_thumbnail(source, song, mood):
    image = ImageOps.fit(source.convert('RGB'), (1280, 720), method=Image.Resampling.LANCZOS)
    image = ImageOps.grayscale(image).convert('RGBA')
    overlay = Image.new('RGBA', image.size)
    draw = ImageDraw.Draw(overlay)
    # A fixed title panel prevents text crossing faces when model framing drifts.
    for x in range(570, 1280):
        alpha = int(245 * min(1, (x-570)/170))
        draw.line((x, 0, x, 720), fill=(9, 9, 9, alpha))
    image = Image.alpha_composite(image, overlay).convert('RGB')
    title = song['title'].split('|')[0].strip()
    hindi = bool(re.search(r'[\u0900-\u097f]', title)) and features.check_feature('raqm')
    if not hindi:
        title = hook_text(song, mood).title()
    draw = ImageDraw.Draw(image)
    for size in range(102, 35, -2):
        face = ImageFont.truetype(str(ASSETS/'NotoSerifDevanagari.ttf'), size) if hindi else font(size)
        lines, line = [], ''
        for word in title.split():
            candidate = (line + ' ' + word).strip()
            if line and draw.textlength(candidate, font=face) > 510:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line: lines.append(line)
        if len(lines) <= 3 and all(draw.textlength(line, font=face) <= 510 for line in lines):
            break
    line_height = int(size*1.45)
    y = 280 - len(lines)*line_height//2
    for line in lines:
        draw.text((720, y), line, font=face, fill='#f6f6f6', stroke_width=1)
        y += line_height
    year = re.search(r'20\d{2}', song['title'])
    label = {'romance': 'Hindi Romantic Song', 'heartbreak': 'Hindi Sad Song',
             'healing': 'Heart Touching Hindi Song'}[mood]
    if year: label += ' ' + year.group()
    draw.rectangle((715, 505, 1238, 555), fill='#e5e5e5')
    draw.text((733, 512), label, font=font(25), fill='#111111')
    draw.text((724, 627), 'HEART & MIND', font=font(20), fill='#dddddd')
    return vintage_finish(image)


def create_artwork(root, song):
    root = Path(root)
    mood = visual_mood(song)
    accent, label, _ = MOODS[mood]
    def compose(kind):
        scene = root/f'{kind}-source.png'
        if not scene.exists():
            raise RuntimeError('Generated song artwork missing; run the images stage first')
        with Image.open(scene) as source:
            base = ImageOps.fit(source.convert('RGB'), (1920, 1080), method=Image.Resampling.LANCZOS)
        overlay = Image.new('RGBA', base.size)
        gradient = ImageDraw.Draw(overlay)
        for x in range(base.width):
            alpha = int(205 * max(0, 1-x/1450))
            gradient.line((x, 0, x, 1080), fill=(8, 12, 24, alpha))
        return Image.alpha_composite(base.convert('RGBA'), overlay).convert('RGB')
    base = compose('background')
    cover = ImageEnhance.Brightness(base).enhance(.88)
    draw = ImageDraw.Draw(cover)
    # Keep the video scene calm; waveform sits below the people, not across their faces.
    draw.text((92, 86), 'HEART & MIND', font=font(28), fill='#f0e9e2')
    draw.text((92, 825), hook_text(song, mood), font=font(64), fill=accent)
    draw.text((96, 918), label, font=font(24), fill='#ffffff')
    cover = vintage_finish(cover)
    cover.save(root/'cover.png')
    with Image.open(root/'thumbnail-source.png') as source:
        thumb = vintage_thumbnail(source, song, mood)
    thumb.save(root/'thumbnail.jpg', quality=92, optimize=True)
