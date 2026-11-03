"""Replay a completed video's real recovery path with the production renderer."""
import argparse
import hashlib
import json
from pathlib import Path

from story_art_style import VERSION, art_prompt
from story_thumbnail import SOURCE_SIZE, EXPORT_SIZE
from story_visual_contract import fallback_contract, thumbnail_recovery


def prepare(kind, output, fixture):
    story = json.loads(Path(fixture).read_text())
    case = story['render_cases'][kind]
    if kind == 'thumbnail':
        selected = thumbnail_recovery(story, 'recorded-production-planner-failure')
        index = selected['thumbnail_scene']
        contract = selected['thumbnail_contract']
        question = selected['thumbnail_question']
    else:
        index = case['scene']
        scene = next(s for s in story['scenes'] if s['index'] == index)
        contract = fallback_contract(scene, story['world'], 'recorded-production-planner-failure', story['characters'])
        question = ''
    scene = next(s for s in story['scenes'] if s['index'] == index)
    width, height = SOURCE_SIZE if kind == 'thumbnail' else (1024, 576)
    plan = dict(kind=kind, source_run=story['source_run'], story_run_id=story['run_id'],
                story_scene=index, narration=scene['text'], authored_visual=scene['visual'],
                story_sha256=hashlib.sha256(json.dumps(story,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
                replay='actual-production-planning-recovery', contract=contract, viewer_question=question,
                prompt=art_prompt(contract['prompt'],kind), art_version=VERSION,
                seed=case['seed'], width=width, height=height, steps=20)
    if kind == 'thumbnail':plan['export_size'] = EXPORT_SIZE
    target = Path(output)/kind/'plan.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
    return plan


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--kind',choices=['background','thumbnail'],required=True)
    parser.add_argument('--output',type=Path,default=Path('output/production-artwork-review'))
    parser.add_argument('--fixture',type=Path,default=Path('tests/fixtures/production-artwork-recovery.json'))
    args=parser.parse_args()
    prepare(args.kind,args.output,args.fixture)
