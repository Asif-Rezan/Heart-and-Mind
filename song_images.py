"""Generate two distinct, reproducible SSD-1B scenes for every original song."""
import hashlib
import json
import os
import re
from pathlib import Path
from PIL import Image
from image_cpu import MODEL, REVISION
from artwork import visual_mood, hook_text


def image_plan(song):
    identity = hashlib.sha256((song['title'] + '\n' + song['lyrics']).encode()).hexdigest()
    mood = visual_mood(song)
    defaults = {
        'romance': 'Sunset park, flowering trees, golden light, warm smiles',
        'heartbreak': 'Adult South Asian woman waiting at rainy train station, wistful face, blue twilight',
        'healing': 'Adult South Asian woman looking toward sunrise in a meadow, hopeful face, warm light',
    }
    plans = []
    for kind, field in (('background', 'background_prompt'), ('thumbnail', 'thumbnail_prompt')):
        scene = song.get(field) or defaults[mood]
        # Put casting/anatomy first: SSD-1B's CLIP encoders truncate long prompts.
        # Avoid contact poses even when an older song.json requests one.
        scene = re.sub(r'\b(?:hugging|embracing|cuddling|kissing|holding hands|close couple)\b',
                       'standing apart', scene, flags=re.I)
        scene = ' '.join(scene.split()[:18]).rstrip(',.;')
        side = 'left' if kind == 'thumbnail' else 'right'
        if mood == 'romance':
            portrait = ('One adult South Asian man and one adult South Asian woman, '
                        'both clean-shaven, separate bodies, visible gap, standing side by side. '
                        f'Two well-lit faces on {side}. ')
        else:
            portrait = f'One adult South Asian woman, clean-shaven face, well-lit portrait on {side}. '
        if kind == 'thumbnail':
            prompt = (portrait + 'Colorful album poster. Title "' + hook_text(song, mood) +
                      '", yellow-white lettering on red brush, right side, clear of faces. ' +
                      scene + '. Fully clothed adults.')
        else:
            prompt = (portrait + 'Colorful music still. ' + scene +
                      '. Fully clothed adults, no lettering.')
        # Seed depends on the song and purpose; never the same fixed seed for every upload.
        seed = int(hashlib.sha256((identity + kind).encode()).hexdigest()[:8], 16)
        plans.append(dict(kind=kind, prompt=prompt,
                          seed=seed, model=MODEL, revision=REVISION,
                          width=int(os.getenv('CPU_IMAGE_WIDTH', '1024')),
                          height=int(os.getenv('CPU_IMAGE_HEIGHT', '576')),
                          steps=int(os.getenv('CPU_IMAGE_STEPS', '16')), allow_text=(kind == 'thumbnail')))
    if song.get('visual_style', 'storybook3d') == 'storybook3d':
        return [storybook_plan(song, mood, plan) for plan in plans]
    if mood == 'romance':
        from couple_background import background_plan
        plans[0] = background_plan(song, plans[0])
    return plans


def storybook_plan(song, mood, base):
    """Generate one coherent scene: no cutouts, painted red palette or model lettering."""
    kind = base['kind']
    subject = ('One adult South Asian man in an oatmeal kurta beside one adult South Asian woman in a sage sari. '
               if mood == 'romance' else 'One adult South Asian woman in a sage outfit. ')
    setting = song.get(kind + '_setting') or song.get('background_setting') or song.get('background_prompt') or {
        'romance': 'cozy bookshop window, wooden shelves, green houseplant',
        'heartbreak': 'quiet railway window, soft rainy daylight',
        'healing': 'meadow, green foliage, clear morning sky',
    }[mood]
    setting = re.sub(r'\b(?:red|ruby|coral|scarlet|cobalt|emerald|golden|cinematic|photography)\b', '', setting, flags=re.I)
    setting = ' '.join(setting.split()[:12]).rstrip(',.;')
    framing = 'Faces toward right, open shelves on left' if kind == 'background' else 'Closer faces, softly focused garden'
    prompt = ('Natural 3D storybook illustration, rounded forms. ' + subject +
              'Chest-up, separate shoulders, gentle expressions. ' + setting + '. ' + framing +
              '. Soft daylight, natural skin, cream, green, wood, muted blue, no lettering.')
    return dict(base, prompt=prompt, style='storybook3d', composition='single-scene',
                style_version=1, allow_text=False,
                extra_negative='red color cast, orange color cast, oversaturated red, neon colors, collage, cutout edges, hands')


def generate_scene(plan, target):
    from image_cpu import generate
    kwargs = dict(seed=plan['seed'], allow_text=plan['allow_text'])
    if 'style' in plan:
        kwargs.update(style=plan['style'], width=plan['width'], height=plan['height'],
                      steps=plan['steps'], extra_negative=plan.get('extra_negative', ''))
    generate(plan['prompt'], target, **kwargs)


def generate_song_images(root, song):
    root = Path(root)
    manifest_path = root/'image-manifest.json'
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    completed = {}
    for plan in image_plan(song):
        kind = plan['kind']
        target = root/f'{kind}-source.png'
        valid = False
        if previous.get(kind) == plan and target.exists():
            try:
                with Image.open(target) as image:
                    image.verify()
                valid = True
            except (OSError, ValueError):
                pass
        if not valid:
            temporary = target.with_suffix('.tmp.png')
            if plan.get('composition') == 'separate-portraits':
                from couple_background import generate_background
                generate_background(root, plan, temporary)
            else:
                generate_scene(plan, temporary)
            with Image.open(temporary) as image:
                image.verify()
            temporary.replace(target)
        completed[kind] = plan
        # Save after each scene so retries preserve completed expensive CPU work.
        temp_manifest = manifest_path.with_suffix('.tmp')
        temp_manifest.write_text(json.dumps(completed, indent=2))
        temp_manifest.replace(manifest_path)
    return completed
