"""Generate a review-only example through the production artwork pipeline."""
import argparse
import json
from pathlib import Path

from artwork import create_artwork
from song_images import image_plan

SONG = {
    'title': 'चाँदनी में तेरा साथ | Chandni Mein Tera Saath | Hindi Romantic Song 2026',
    'lyrics': '[Verse 1]\nपुरानी किताबों में तेरा खत मिला\nखामोश शामों को नया साथ मिला\n[Chorus]\nतेरे साथ ये चाँदनी गुनगुनाए\nहर पन्ना मुझे तेरे पास बुलाए\n',
    'prompt': 'Hindi romantic acoustic pop, intimate melodic vocal, warm guitar and piano',
    'description': 'An original Hindi romantic song about reuniting in a moonlit old bookshop.',
    'duration': 195,
    'visual_mood': 'romance',
    'visual_style': 'illustration',
    'background_setting': 'old bookshop, wooden shelves, amber lantern beside a blue moonlit window',
    'thumbnail_text': 'TERE SAATH',
    'background_prompt': 'Moonlit old bookshop, tender smiles beside wooden shelves, golden lantern light, cobalt moonlit window, ruby and emerald clothing.',
    'thumbnail_prompt': 'Colorful old bookshop, tender smiles, wooden shelves, cobalt moonlight through window, warm lantern glow, ruby and emerald clothing.',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=['background', 'background-man', 'background-woman', 'background-scenery', 'thumbnail', 'compose'], required=True)
    parser.add_argument('--output', type=Path, default=Path('output/artwork-demo'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'song.json').write_text(json.dumps(SONG, ensure_ascii=False, indent=2))
    if args.kind == 'compose':
        from couple_background import compose_background_files
        plan = json.loads((args.output/'background-plan.json').read_text())
        temporary = args.output/'background-source.tmp.png'
        compose_background_files(args.output, plan, temporary)
        temporary.replace(args.output/'background-source.png')
        (args.output/'background-plan.json').write_text(json.dumps(plan, indent=2))
        create_artwork(args.output, SONG)
    elif args.kind.startswith('background'):
        from couple_background import generate_background, generate_background_part
        plan = image_plan(SONG)[0]
        if args.kind == 'background':
            generate_background(args.output, plan, args.output/'background-source.png')
        else:
            generate_background_part(args.output, plan, args.kind.split('-', 1)[1])
        (args.output/'background-plan.json').write_text(json.dumps(plan, indent=2))
    else:
        from image_cpu import generate
        plan = next(plan for plan in image_plan(SONG) if plan['kind'] == args.kind)
        # Review an illustration experiment without changing production's photo default.
        scene = 'pink flowering garden, golden sunset'
        plan['prompt'] = (
            'Gouache illustration. Exactly two adults, chest-up, hands below frame. '
            'Left: handsome man, short black hair, square jaw, clean-shaven, plain blue kurta. '
            'Right: beautiful woman, long black hair, red sari, gold earrings. '
            'Two separate shoulders, wide visible gap. Gentle smiles, looking toward viewer. '
            + scene + '. Rich teal and coral, textured paper, fully clothed, no lettering.')
        plan['style'] = 'illustration'
        plan['allow_text'] = False
        generate(plan['prompt'], args.output/f'{args.kind}-source.png', seed=plan['seed'], allow_text=plan['allow_text'], style=plan['style'])
        (args.output/f'{args.kind}-plan.json').write_text(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()
