"""Generate two distinct, reproducible SSD-1B scenes for every original song."""
import hashlib
import json
import os
from pathlib import Path
from PIL import Image
from image_cpu import MODEL, REVISION
from artwork import visual_mood, hook_text


def image_plan(song):
    identity = hashlib.sha256((song['title'] + '\n' + song['lyrics']).encode()).hexdigest()
    mood = visual_mood(song)
    defaults = {
        'romance': 'Adult South Asian couple walking together, warm smiles, sunset park, golden light',
        'heartbreak': 'Adult South Asian woman waiting at rainy train station, wistful face, blue twilight',
        'healing': 'Adult South Asian woman looking toward sunrise in a meadow, hopeful face, warm light',
    }
    plans = []
    for kind, field in (('background', 'background_prompt'), ('thumbnail', 'thumbnail_prompt')):
        scene = song.get(field) or defaults[mood]
        # Keep exact lettering and layout ahead of scenic detail in the encoder.
        scene = ' '.join(scene.split()[:18 if kind == 'thumbnail' else 26]).rstrip(',.;')
        if kind == 'thumbnail':
            portrait = ('exactly one adult couple, two large well-lit faces on left' if mood == 'romance'
                        else 'one adult lead, large well-lit face on left')
            prompt = ('Vibrant colorful romantic album poster. Title "' + hook_text(song, mood) +
                '", bold yellow-white lettering on red brush, right side, clear of faces. ' +
                portrait + '. ' + scene + '. Golden light, fully clothed adults, full-frame scenery.')
        else:
            prompt = ('Bright colorful romantic music still, medium portrait on right, clearly lit faces. ' +
                scene + '. Golden face light, vivid blue backdrop, rich colors, fully clothed adults, no lettering.')
        # Seed depends on the song and purpose; never the same fixed seed for every upload.
        seed = int(hashlib.sha256((identity + kind).encode()).hexdigest()[:8], 16)
        plans.append(dict(kind=kind, prompt=prompt,
                          seed=seed, model=MODEL, revision=REVISION,
                          width=int(os.getenv('CPU_IMAGE_WIDTH', '1024')),
                          height=int(os.getenv('CPU_IMAGE_HEIGHT', '576')),
                          steps=int(os.getenv('CPU_IMAGE_STEPS', '16')), allow_text=(kind == 'thumbnail')))
    return plans


def generate_song_images(root, song):
    from image_cpu import generate
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
            generate(plan['prompt'], temporary, seed=plan['seed'], allow_text=plan['allow_text'])
            with Image.open(temporary) as image:
                image.verify()
            temporary.replace(target)
        completed[kind] = plan
        # Save after each scene so retries preserve completed expensive CPU work.
        temp_manifest = manifest_path.with_suffix('.tmp')
        temp_manifest.write_text(json.dumps(completed, indent=2))
        temp_manifest.replace(manifest_path)
    return completed
