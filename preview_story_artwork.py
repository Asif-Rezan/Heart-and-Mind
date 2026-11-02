"""Review-only images using the same art direction and model as story production."""
import argparse
import json
from pathlib import Path
from story_art_style import art_prompt, VERSION
from story_image_cpu import generate, MODEL, REVISION, negative_prompt, GUIDANCE_SCALE

SCENES = {
    'background': 'Adult Indian woman discovering a locked wooden chest in a cozy attic, holding a brass key, curious expression, turquoise sari, dark braid, warm sunset through round window.',
    'thumbnail': 'Adult Indian woman raising a brass key beside her surprised face, mysterious glowing wooden chest in foreground, contents hidden, turquoise sari, dark braid, teal attic, warm golden light.',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=SCENES, required=True)
    parser.add_argument('--output', type=Path, default=Path('output/story-artwork-preview'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    prompt = art_prompt(SCENES[args.kind], args.kind)
    plan = dict(prompt=prompt, art_version=VERSION, model=MODEL, revision=REVISION,
                seed=1142 if args.kind == 'background' else 7042, steps=20,
                width=1024, height=576, negative_prompt=negative_prompt(), guidance_scale=GUIDANCE_SCALE)
    (args.output/f'{args.kind}-plan.json').write_text(json.dumps(plan, indent=2))
    generate(prompt, args.output/f'{args.kind}.png', seed=plan['seed'], steps=plan['steps'])


if __name__ == '__main__':
    main()
