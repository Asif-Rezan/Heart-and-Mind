"""Compose song-specific artwork from two freshly generated cinematic scenes.

The SSD-1B image job supplies a separate background and thumbnail source.
"""
from pathlib import Path
import re
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ASSETS = Path(__file__).resolve().parent / 'assets' / 'artwork'
MOODS = {
    'romance': ('#ffdf96', 'HINDI LOVE SONG', 'TERE SAATH'),
    'heartbreak': ('#c4dcff', 'HINDI SAD SONG', 'ANKAHI BAATEIN'),
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


def create_artwork(root, song):
    root = Path(root)
    mood = visual_mood(song)
    accent, label, _ = MOODS[mood]
    def compose(kind):
        scene = root/('scene-000.png' if kind == 'background' else 'thumbnail-source.png')
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
    cover.save(root/'cover.png')
    thumb = compose('thumbnail').resize((1280, 720), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(thumb)
    draw.rounded_rectangle((62, 130, 410, 176), radius=8, fill=accent)
    draw.text((78, 139), label, font=font(22), fill='#141820')
    draw_hook(thumb, hook_text(song, mood), accent)
    draw.text((64, 625), 'HEART & MIND', font=font(20), fill='#ffffff')
    thumb.save(root/'thumbnail.jpg', quality=92, optimize=True)
