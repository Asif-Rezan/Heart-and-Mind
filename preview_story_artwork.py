"""Review-only images using the same art direction and model as story production."""
import argparse
import json
from pathlib import Path
from story_art_style import art_prompt, VERSION
from story_thumbnail import SOURCE_SIZE, EXPORT_SIZE, export_thumbnail
from story_image_cpu import generate, MODEL, REVISION, negative_prompt, GUIDANCE_SCALE

SCENES = {
    'background': 'Beautiful adult Indian woman, long dark braid, turquoise sari, discovering a locked wooden chest in a sunlit attic, holding a brass key, curious expression, warm golden rays.',
    'thumbnail': 'Large partly-open wooden chest in foreground, golden light through narrow lid gap, contents hidden. Beautiful adult Indian woman beside chest, turquoise sari, long dark braid, wide-eyed surprise, raising brass key.',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=SCENES, required=True)
    parser.add_argument('--output', type=Path, default=Path('output/story-artwork-preview'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    prompt = art_prompt(SCENES[args.kind], args.kind)
    width, height = SOURCE_SIZE if args.kind == 'thumbnail' else (1024, 576)
    plan = dict(prompt=prompt, art_version=VERSION, model=MODEL, revision=REVISION,
                seed=1142 if args.kind == 'background' else 8042, steps=20,
                width=width, height=height, negative_prompt=negative_prompt(), guidance_scale=GUIDANCE_SCALE)
    if args.kind == 'thumbnail':
        plan.update(export_size=EXPORT_SIZE, crop='center to 16:9', resampling='lanczos')
    (args.output/f'{args.kind}-plan.json').write_text(json.dumps(plan, indent=2))
    generate(prompt, args.output/f'{args.kind}.png', seed=plan['seed'], steps=plan['steps'],
             width=width, height=height)
    if args.kind == 'thumbnail':
        export_thumbnail(args.output/'thumbnail.png', args.output/'thumbnail.jpg')


if __name__ == '__main__':
    main()
