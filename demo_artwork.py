"""Generate a review-only example through the production artwork pipeline."""
import argparse
import json
from pathlib import Path

from artwork import create_artwork
from song_images import image_plan, generate_scene

SONG = {
    'title': 'चाँदनी में तेरा साथ | Chandni Mein Tera Saath | Hindi Romantic Song 2026',
    'lyrics': '[Verse 1]\nपुरानी किताबों में तेरा खत मिला\nखामोश शामों को नया साथ मिला\n[Chorus]\nतेरे साथ ये चाँदनी गुनगुनाए\nहर पन्ना मुझे तेरे पास बुलाए\n',
    'prompt': 'Hindi romantic acoustic pop, intimate melodic vocal, warm guitar and piano',
    'description': 'An original Hindi romantic song about reuniting in a moonlit old bookshop.',
    'duration': 195,
    'visual_mood': 'romance',
    'visual_style': 'storybook3d',
    'background_setting': 'sunlit bookshop, open window, wooden shelves, green houseplant',
    'thumbnail_setting': 'sunlit window, green garden, softly focused wooden shelves',
    'thumbnail_text': 'TERE SAATH',
    'background_prompt': 'Moonlit old bookshop, tender smiles beside wooden shelves, golden lantern light, cobalt moonlit window, ruby and emerald clothing.',
    'thumbnail_prompt': 'Colorful old bookshop, tender smiles, wooden shelves, cobalt moonlight through window, warm lantern glow, ruby and emerald clothing.',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=['background', 'thumbnail', 'compose'], required=True)
    parser.add_argument('--output', type=Path, default=Path('output/artwork-demo'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'song.json').write_text(json.dumps(SONG, ensure_ascii=False, indent=2))
    if args.kind == 'compose':
        create_artwork(args.output, SONG)
    else:
        plan = next(plan for plan in image_plan(SONG) if plan['kind'] == args.kind)
        generate_scene(plan, args.output/f'{args.kind}-source.png')
        (args.output/f'{args.kind}-plan.json').write_text(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()
