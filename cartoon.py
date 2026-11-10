"""Active English family cartoon CLI; existing publication checkpoints are reused."""
import argparse
import gc
import hashlib
import json
import os
from pathlib import Path
import re
from cartoon_story import plan, validate_manifest, atomic, VERSION


def prepare(run_id, stage, topic):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',run_id): raise ValueError('Invalid cartoon run ID')
    root = Path('output')/run_id; root.mkdir(parents=True,exist_ok=True)
    if stage == 'story':
        from storage import Store
        history = Store().load('history.json',[]) if os.getenv('DRIVE_TOKEN_JSON') else []
        if (root/'song.json').exists():
            song = validate_manifest(json.loads((root/'song.json').read_text()))
            draft = json.loads((root/'cartoon-draft.json').read_text())
            if draft['identity']['topic'] != topic: raise ValueError('Saved topic differs; use a new run ID')
        else: song = plan(root,run_id,topic,history)
        import lyrics_cpu
        if lyrics_cpu._model is not None: lyrics_cpu._model.close(); lyrics_cpu._model = None
        gc.collect()
        return
    if stage == 'speech':
        from cartoon_audio import prepare_audio
        prepare_audio(root); return
    song = validate_manifest(json.loads((root/'song.json').read_text()),timed=True)
    if stage == 'images':
        from image_cpu import generate
        from cartoon_render import render_shot
        shard, count = int(os.getenv('IMAGE_SHARD','0')), int(os.getenv('IMAGE_SHARDS','20'))
        if not 0 <= shard < count: raise ValueError('Invalid cartoon image shard')
        # Generate all shard illustrations, then release diffusion before segmentation.
        for scene in song['scenes']:
            if scene['index']%count != shard: continue
            source = root/f"scene-{scene['index']:03d}-source.png"
            key = hashlib.sha256((VERSION+scene['prompt']).encode()).hexdigest()
            record = source.with_suffix('.json')
            from cartoon_audio import digest
            cached = False
            try:
                saved = json.loads(record.read_text()); cached = saved == dict(identity=key,sha256=digest(source))
            except (OSError,ValueError): pass
            if not cached:
                temp = source.with_suffix('.tmp.png')
                generate(scene['prompt'],temp,seed=int(key[:8],16),width=1024,height=576,steps=16)
                from PIL import Image
                with Image.open(temp) as im: im.verify()
                temp.replace(source); atomic(record,dict(identity=key,sha256=digest(source)))
        import image_cpu
        image_cpu._pipeline = None; gc.collect()
        for scene in song['scenes']:
            if scene['index']%count == shard: render_shot(root,scene)
        if shard == 0:
            # Thumbnail is the actual opening story scene, not an unrelated toddler image.
            import shutil
            shutil.copyfile(root/'scene-000-source.png',root/'thumbnail-source.png')
        return
    if stage == 'render':
        from cartoon_render import assemble, is_current
        if not is_current(root): assemble(root)
    elif stage == 'publish':
        from pipeline import run
        run(run_id,defer_drive_cleanup=True)
    else: raise ValueError('Unknown cartoon stage')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--stage',choices=['story','speech','images','render','publish'],required=True)
    parser.add_argument('--topic',default='A funny everyday misunderstanding resolved through cooperation')
    args = parser.parse_args()
    try: prepare(args.run_id,args.stage,args.topic)
    except Exception as error:
        if re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.run_id):
            atomic(Path('output')/args.run_id/'cartoon-failure.json',dict(stage=args.stage,error_type=type(error).__name__,message=str(error)[:700]))
        raise
