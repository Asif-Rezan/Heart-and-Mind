"""Exercise real production artwork plans before spending hours on music synthesis."""
import json
import os
from pathlib import Path

from authored_song import load_authored_song
from music_short import companion
from music_video import image_plan
from story_image_review import generate_reviewed
from story_writer import save_json


def main():
    kind=os.getenv('IMAGE_KIND','thumbnail')
    if kind not in ('background','thumbnail','portrait'):
        raise ValueError('Unsupported preview kind')
    song=load_authored_song(os.getenv('AUTHORED_SONG','ab-baat-karein-2026-11-03'))
    if kind=='portrait':song=companion(song,'artwork-readiness')
    plan=image_plan(song,{},0,'thumbnail' if kind=='thumbnail' else 'background')
    out=Path('output/romantic-couple-test')/kind;out.mkdir(parents=True,exist_ok=True)
    save_json(out/'plan.json',plan)
    report=generate_reviewed(plan['prompt'],out/(kind+'.png'),seed=plan['seed'],
        contract=plan['contract'],kind=plan['kind'],width=plan['width'],height=plan['height'],steps=plan['steps'])
    save_json(out/'review.json',report)
    print(json.dumps(dict(phase='production artwork readiness',kind=kind,
        passed=report['passed'],width=plan['width'],height=plan['height'])),flush=True)


if __name__=='__main__':main()
