"""Build romantic backgrounds from independent scenery and portrait generations."""
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageOps

COMPOSITION_VERSION = 1
CUTOUT_MODEL = 'u2net'


def background_plan(song, base):
    style = song.get('visual_style', 'illustration')
    if style not in ('photo', 'illustration'):
        raise ValueError('Unsupported background visual_style')
    look = ('Hand-painted gouache illustration, textured paper, rich teal and coral.'
            if style == 'illustration' else 'Colorful editorial photograph, natural skin.')
    lighting = 'Warm frontal light, soft shadows, eye-level view.'
    # New songs can provide a people-free setting. Strip casting from legacy scenes.
    scene = song.get('background_setting') or song.get('background_prompt') or 'flowering garden at sunset'
    scene = re.sub(r'\b(?:adult|South Asian|couple|man|woman|people|two|original|fully clothed|'
                   r'hugging|embracing|kissing|cuddling|holding hands|standing apart|'
                   r'tender smiles|warm smiles|colorful clothing|ruby and emerald clothing|cinematic photography|realistic skin)\b',
                   '', scene, flags=re.I)
    scene = ' '.join(scene.split()[:24]).strip(' ,.;')
    subjects = {
        'scenery': ('Empty unoccupied setting: ' + scene + '. ' + look + ' ' + lighting,
                    1024, 576, 'people, person, faces, man, woman, couple, human figures, portraits'),
        'man': ('One adult South Asian man alone, short black hair, masculine square jaw, '
                'clean-shaven, plain blue kurta. Centered chest-up portrait, entire head and shoulders visible, '
                'gentle smile, hands below frame, plain ivory background. ' + look + ' ' + lighting,
                512, 768, 'woman, sari, earrings, necklace, forehead jewelry, second person, hands, fingers'),
        'woman': ('One adult South Asian woman alone, long black hair, red sari, small gold earrings. '
                  'Centered chest-up portrait, entire head and shoulders visible, gentle smile, '
                  'hands below frame, plain ivory background. ' + look + ' ' + lighting,
                  512, 768, 'man, beard, mustache, second person, hands, fingers'),
    }
    parts = []
    for role, (prompt, width, height, negative) in subjects.items():
        seed = int(hashlib.sha256(f"{base['seed']}:{role}".encode()).hexdigest()[:8], 16)
        parts.append(dict(role=role, prompt=prompt, seed=seed, width=width, height=height,
                          style=style, extra_negative=negative, allow_text=False, people=(role != 'scenery'),
                          model=base['model'], revision=base['revision'], steps=base['steps']))
    return dict(base, composition='separate-portraits', composition_version=COMPOSITION_VERSION,
                cutout_model=CUTOUT_MODEL, parts=parts)


def checked_cutout(image, session):
    from rembg import remove
    cutout = remove(image.convert('RGB'), session=session).convert('RGBA')
    alpha = cutout.getchannel('A')
    mask = alpha.point(lambda value: 255 if value > 16 else 0)
    area = sum(mask.histogram()[1:]) / (mask.width * mask.height)
    if not 0.02 < area < 0.98:
        raise ValueError('Portrait background removal failed; inspect source and retry')
    return cutout.crop(mask.getbbox())


def compose_background(scenery, man, woman, size):
    """Fit portraits into disjoint boxes; preserve faces and reserve left overlay space."""
    canvas = ImageOps.fit(scenery.convert('RGB'), size, method=Image.Resampling.LANCZOS).convert('RGBA')
    width, height = size
    for portrait, left, right in ((man, 0.39, 0.65), (woman, 0.70, 0.96)):
        # The bounds guarantee a gap even if segmentation leaves stray pixels.
        box_width = int(width * right) - int(width * left)
        figure = ImageOps.contain(portrait.convert('RGBA'), (box_width, int(height * 0.90)),
                                 method=Image.Resampling.LANCZOS)
        x = int(width * left) + (box_width - figure.width) // 2
        canvas.alpha_composite(figure, (x, height - figure.height))
    return canvas.convert('RGB')


def generate_background_part(root, plan, role):
    """Cache one independent scene, usable by separate GitHub matrix runners."""
    from image_cpu import generate
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    part = next(part for part in plan['parts'] if part['role'] == role)
    source = root / f'background-{role}.png'
    checkpoint = source.with_suffix('.json')
    valid = False
    if source.exists() and checkpoint.exists():
        try:
            valid = json.loads(checkpoint.read_text()) == part
            with Image.open(source) as image:
                image.verify()
        except (OSError, ValueError):
            valid = False
    if not valid:
        temporary = source.with_suffix('.tmp.png')
        generate(part['prompt'], temporary, seed=part['seed'], allow_text=False,
                 style=part['style'], width=part['width'], height=part['height'],
                 extra_negative=part['extra_negative'], people=part['people'], steps=part['steps'])
        with Image.open(temporary) as image:
            image.verify()
        temporary.replace(source)
        tmp_checkpoint = checkpoint.with_suffix('.tmp')
        tmp_checkpoint.write_text(json.dumps(part, indent=2))
        tmp_checkpoint.replace(checkpoint)
    return source


def compose_background_files(root, plan, target):
    from rembg import new_session
    root = Path(root)
    session = new_session(plan['cutout_model'], providers=['CPUExecutionProvider'])
    cutouts = {}
    for role in ('man', 'woman'):
        source = root / f'background-{role}.png'
        checkpoint = source.with_suffix('.json')
        expected = next(part for part in plan['parts'] if part['role'] == role)
        if json.loads(checkpoint.read_text()) != expected:
            raise ValueError('Portrait checkpoint does not match requested background')
        with Image.open(source) as image:
            cutouts[role] = checked_cutout(image, session)
        cutouts[role].save(root / f'background-{role}-cutout.png')
    scenery = root / 'background-scenery.png'
    expected = next(part for part in plan['parts'] if part['role'] == 'scenery')
    if json.loads(scenery.with_suffix('.json').read_text()) != expected:
        raise ValueError('Scenery checkpoint does not match requested background')
    with Image.open(scenery) as image:
        composed = compose_background(image, cutouts['man'], cutouts['woman'],
                                      (plan['width'], plan['height']))
    composed.save(target)


def generate_background(root, plan, target):
    """Checkpoint expensive generations before cutting out and compositing."""
    for part in plan['parts']:
        generate_background_part(root, plan, part['role'])
    compose_background_files(root, plan, target)
