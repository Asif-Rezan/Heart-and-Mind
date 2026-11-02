"""Transfer only a shard's owned images and verified-clip inputs."""
import argparse
import json
from pathlib import Path
import re
import shutil
from story_writer import save_json, StoryValidationError


def copy_owned(root, target, shard, shards):
    root, target = Path(root), Path(target)
    manifest = root/f'image-manifest-{shard:02d}.json'
    if not manifest.is_file():
        raise StoryValidationError('image_artifact_manifest_missing',dict(shard=shard))
    plans = json.loads(manifest.read_text())
    owned = {key:value for key,value in plans.items() if int(key)%shards == shard}
    if len(owned) != len(plans):
        raise StoryValidationError('image_artifact_ownership_mismatch',dict(shard=shard,shards=shards))
    target.mkdir(parents=True,exist_ok=True)
    save_json(target/manifest.name,owned)
    names = [f'scene-{int(i):03d}-source.png' for i in owned]
    for i in owned:
        names += [f'story-motion/clip-{int(i):03d}.mp4',f'story-motion/clip-{int(i):03d}.json']
    names += [f'cast-reference-{shard:02d}.png',f'cast-reference-{shard:02d}.json']
    if shard == 0:
        names += ['thumbnail-source.png','thumbnail-manifest.json']
    for name in names:
        source=root/name
        if source.is_file():
            destination=target/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)


def restore_images(source, destination, run_id, shards=None):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',run_id):
        raise ValueError('Invalid story run identity')
    artifacts=[]
    for artifact in Path(source).iterdir():
        match=re.fullmatch(r'story-images-\d+-(\d+)',artifact.name)
        if match and (artifact/run_id).is_dir():
            artifacts.append((int(match[1]),artifact/run_id))
    if not artifacts:
        raise StoryValidationError('image_artifacts_missing')
    shards=shards or max(i for i,_ in artifacts)+1
    for shard,root in sorted(artifacts):
        if not 0<=shard<shards:
            raise StoryValidationError('image_artifact_ownership_mismatch',dict(shard=shard,shards=shards))
        copy_owned(root,Path(destination)/run_id,shard,shards)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['pack','restore'])
    parser.add_argument('--source',required=True)
    parser.add_argument('--destination',required=True)
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--shard',type=int)
    parser.add_argument('--shards',type=int)
    args=parser.parse_args()
    if args.mode=='restore':
        restore_images(args.source,args.destination,args.run_id,args.shards)
    else:
        if args.shard is None or not args.shards or not 0<=args.shard<args.shards:
            parser.error('pack requires valid --shard and --shards')
        copy_owned(Path(args.source)/args.run_id,Path(args.destination)/args.run_id,args.shard,args.shards)
