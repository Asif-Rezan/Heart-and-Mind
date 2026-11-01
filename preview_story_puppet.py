"""Create a local four-second puppet preview; no credentials or model downloads."""
import argparse
from pathlib import Path
from story_puppet import Stage, scene_plan, encode
from story_writer import save_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='docs/puppet-preview')
    args=parser.parse_args()
    story=dict(characters='Ram, young Indian man, short black hair, blue kurta. Sita, Indian woman, green sari and long black hair.',
        world='Indian village',scenes=[dict(index=0,visual='Ram offers a letter to Sita together in their shop, happy smiles.')])
    plan=scene_plan(story,dict(index=0))
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    save_json(out/'scene-plan.json',plan)
    Stage(plan).frame(.7,False).save(out/'story-frame.png')
    encode(plan,out/'puppet-demo.mp4',100,25,960,540)
    print(out/'puppet-demo.mp4')


if __name__=='__main__':main()
