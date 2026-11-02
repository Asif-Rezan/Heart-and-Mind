"""Preview actual story events using the production planner, generator and visual gate."""
import argparse
import hashlib
import json
from pathlib import Path
from story_art_style import art_prompt, VERSION
from story_thumbnail import SOURCE_SIZE, EXPORT_SIZE, export_thumbnail
from story_visual_contract import validate_contract


def load_story(path):
    path = Path(path)
    if path.is_dir():
        found = list(path.rglob('story.json'))
        if len(found) != 1:raise ValueError('Preview requires exactly one completed story.json')
        path = found[0]
    return json.loads(path.read_text())


def opening_thumbnail_recovery(plan,background):
    """Apply the production opening-scene fallback when rerendering an old failed plan."""
    if plan['contract'].get('planning_review',{}).get('passed') is True:return plan
    if background.get('story_sha256')!=plan.get('story_sha256') or background.get('story_scene')!=0:return plan
    import copy
    from story_visual_contract import REVIEW_VERSION
    result=copy.deepcopy(plan);contract=copy.deepcopy(background['contract'])
    validate_contract(contract,dict(text=background['narration']))
    contract['fallback']=dict(mode='scene-recovery',literal_event=contract['event'],reason='thumbnail_planning_rejected')
    contract['planning_review']=dict(version=REVIEW_VERSION,passed=False,issues=['Opening-scene thumbnail recovery; not approved by planning audit.'])
    anchor=contract['checks'][0]['answers'][0]
    result.update(story_scene=0,narration=background['narration'],contract=contract,
        viewer_question='What will happen next to the '+anchor+'?',prompt=art_prompt(contract['prompt'],'thumbnail'),
        width=SOURCE_SIZE[0],height=SOURCE_SIZE[1],export_size=EXPORT_SIZE,recovery_from_story_scene=0)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['plan','generate','audit','audit-plan'], required=True)
    parser.add_argument('--kind', choices=['background','thumbnail'], default='thumbnail')
    parser.add_argument('--story', type=Path, default=Path('tests/fixtures/production-artwork-story.json'))
    parser.add_argument('--scene-index', type=int, default=0)
    parser.add_argument('--output', type=Path, default=Path('output/story-artwork-preview'))
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    if args.stage == 'audit':
        from story_image_review import review_image
        rejected = review_image('tests/fixtures/rejected-letter-portrait.jpg',[
            dict(question='What is the man holding in his hands?',answers=['letter','envelope','paper'])])
        (args.output/'rejected-portrait-review.json').write_text(json.dumps(rejected,indent=2))
        print(json.dumps(rejected),flush=True)
        if rejected['passed']:raise RuntimeError('Visual gate failed to reject the actual portrait-only regression')
        return
    if args.stage == 'audit-plan':
        from story_visual_contract import assess_plan
        for name in ('notebook','toy'):
            old=json.loads(Path(f'tests/fixtures/rejected-{name}-plan.json').read_text())
            verdict=assess_plan(old['contract'],dict(text=old['narration']),old['cast'],
                load_story(args.story)['world'],73192,args.output/f'rejected-{name}-review-raw.json',
                old['viewer_question'] or None)
            filename='rejected-plan-review.json' if name=='notebook' else 'rejected-toy-review.json'
            (args.output/filename).write_text(json.dumps(verdict,indent=2))
            print(json.dumps(verdict),flush=True)
            if verdict['passed']:raise RuntimeError(f'Planner reviewer accepted the actual invented-{name} regression')
        return
    root = args.output / args.kind
    root.mkdir(parents=True,exist_ok=True)
    plan_path = root/'plan.json'
    if args.stage == 'plan':
        from story_plan import visual_batch, thumbnail_plan
        story = load_story(args.story)
        identity=hashlib.sha256(json.dumps(story,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if args.kind == 'thumbnail':
            selected = thumbnail_plan(root,story,identity)
            index, contract = selected['thumbnail_scene'], selected['thumbnail_contract']
            question = selected['thumbnail_question']
        else:
            index = args.scene_index
            if not 0 <= index < len(story['scenes']):raise ValueError('Preview scene index outside story')
            contract = visual_batch(root,story,[index],identity)[str(index)]
            question = ''
        validate_contract(contract,story['scenes'][index])
        width,height=SOURCE_SIZE if args.kind=='thumbnail' else (1024,576)
        plan=dict(kind=args.kind,story_run_id=story['run_id'],story_title=story['title'],
                  story_sha256=identity,story_scene=index,narration=story['scenes'][index]['text'],
                  cast=story['characters'],viewer_question=question,contract=contract,
                  prompt=art_prompt(contract['prompt'],args.kind),art_version=VERSION,
                  seed=int(identity[:8],16)+(0 if args.kind=='background' else 7001),
                  width=width,height=height,steps=20)
        if args.kind=='thumbnail':plan['export_size']=EXPORT_SIZE
        plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
        return
    from story_image_review import generate_reviewed
    plan=json.loads(plan_path.read_text())
    background_plan=args.output/'background'/'plan.json'
    if args.kind=='thumbnail' and background_plan.is_file():
        plan=opening_thumbnail_recovery(plan,json.loads(background_plan.read_text()))
    validate_contract(plan['contract'],dict(text=plan['narration']))
    plan['planning_art_version']=plan.get('planning_art_version',plan['art_version'])
    plan['art_version']=VERSION
    plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2))
    source=root/f'{args.kind}-source.png'
    review=generate_reviewed(plan['prompt'],source,seed=plan['seed'],contract=plan['contract'],
                             kind=args.kind,width=plan['width'],height=plan['height'],steps=plan['steps'])
    (root/'review.json').write_text(json.dumps(review,indent=2))
    if args.kind=='thumbnail':export_thumbnail(source,root/'thumbnail.jpg')


if __name__ == '__main__':main()
