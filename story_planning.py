"""Independent planning workers consume one sealed, immutable spoken script."""
import copy
import hashlib
import json
from pathlib import Path
from story_writer import validate_story,save_json,StoryValidationError

from story_visual_contract import VERSION as VISUAL_VERSION, validate_contract, install_visuals

VISUAL_WORKERS=18
THUMBNAIL_FIELDS={'thumbnail_scene','thumbnail_prompt','thumbnail_contract','thumbnail_question'}


def visual_worker_count(story):
    return min(VISUAL_WORKERS,len(story['scenes']))


def prose_identity(story):
    return hashlib.sha256(json.dumps(story,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def load_prose(root,run_id):
    path=Path(root)/'story-prose.json'
    if not path.is_file():raise StoryValidationError('planning_prose_missing')
    story=validate_story(json.loads(path.read_text()),require_planning=False)
    if story['run_id']!=run_id:raise StoryValidationError('story_identity_mismatch')
    return story


def visual_indices(story,part):
    workers=visual_worker_count(story)
    if type(part) is not int or not 0<=part<workers:
        raise StoryValidationError('planning_worker_invalid',dict(part=part))
    return list(range(part*len(story['scenes'])//workers,(part+1)*len(story['scenes'])//workers))


def worker_path(root,kind,part=None):
    if kind not in ('seo','thumbnail','visual'):raise StoryValidationError('planning_worker_invalid')
    return Path(root)/f"planning-{kind}{'-'+str(part) if kind=='visual' else ''}.json"


def validate_payload(kind,payload,story,part=None):
    if not isinstance(payload,dict):raise StoryValidationError('planning_payload_invalid',dict(kind=kind,part=part))
    if kind=='visual':
        if (set(payload)!={str(i) for i in visual_indices(story,part)} or
                any(not isinstance(v,dict) for v in payload.values())):
            raise StoryValidationError('planning_visual_coverage',dict(part=part))
        try:
            for key,value in payload.items():validate_contract(value,story['scenes'][int(key)])
        except ValueError as exc:raise StoryValidationError('planning_visual_contract_invalid') from exc
    elif kind=='thumbnail':
        if (set(payload)!=THUMBNAIL_FIELDS or
                type(payload['thumbnail_scene']) is not int or not 0<=payload['thumbnail_scene']<len(story['scenes']) or
                not isinstance(payload['thumbnail_prompt'],str) or not 80<=len(payload['thumbnail_prompt'])<=360):
            raise StoryValidationError('planning_payload_invalid',dict(kind=kind))
        try:
            validate_contract(payload['thumbnail_contract'],story['scenes'][payload['thumbnail_scene']])
            if payload['thumbnail_contract']['prompt']!=payload['thumbnail_prompt'] or not isinstance(payload['thumbnail_question'],str) or not payload['thumbnail_question'].strip():raise ValueError()
        except ValueError as exc:raise StoryValidationError('planning_thumbnail_contract_invalid') from exc
    elif kind=='seo':
        from story_packaging import clean_tags
        if (set(payload)!=set(('title','description','tags')) or not isinstance(payload['title'],str) or
                not 1<=len(payload['title'])<=100 or not isinstance(payload['description'],str) or
                not 1<=len(payload['description'])<=4400 or not isinstance(payload['tags'],list) or
                len(payload['tags'])<6 or not all(isinstance(v,str) for v in payload['tags']) or
                clean_tags(payload['tags'])!=payload['tags']):
            raise StoryValidationError('planning_payload_invalid',dict(kind=kind))
    return payload


def run_worker(root,run_id,kind,part=None):
    root=Path(root);story=load_prose(root,run_id);identity=prose_identity(story)
    slots=visual_indices(story,part) if kind=='visual' else None
    path=worker_path(root,kind,part)
    if path.exists():
        saved=json.loads(path.read_text())
        if saved.get('prose_identity')==identity and saved.get('kind')==kind and saved.get('part')==part and (kind=='seo' or saved.get('visual_plan_version')==VISUAL_VERSION):
            try:
                validate_payload(kind,saved.get('payload'),story,part)
                return saved
            except StoryValidationError:
                pass  # Regenerate only this corrupt local worker checkpoint.
    if kind=='seo':
        from story_packaging import prepare_packaging
        prepare_packaging(root,story)
        payload={key:story[key] for key in ('title','description','tags')}
    elif kind=='thumbnail':
        from story_plan import thumbnail_plan
        payload=thumbnail_plan(root,story,identity)
    else:
        from story_plan import visual_batch
        payload=visual_batch(root,story,slots,identity)
    validate_payload(kind,payload,story,part)
    saved=dict(version='parallel-planning-v1',visual_plan_version=VISUAL_VERSION,prose_identity=identity,run_id=run_id,kind=kind,part=part,payload=payload)
    save_json(path,saved)
    print(json.dumps(dict(phase='planning worker complete',kind=kind,part=part,scenes=len(slots or []))),flush=True)
    return saved


def join_planning(root,run_id):
    root=Path(root);prose=load_prose(root,run_id);identity=prose_identity(prose)
    def read(kind,part=None):
        path=worker_path(root,kind,part)
        if not path.is_file():raise StoryValidationError('planning_output_missing',dict(kind=kind,part=part))
        saved=json.loads(path.read_text())
        if (saved.get('prose_identity')!=identity or saved.get('run_id')!=run_id or
                saved.get('kind')!=kind or saved.get('part')!=part or
                (kind!='seo' and saved.get('visual_plan_version')!=VISUAL_VERSION)):
            raise StoryValidationError('planning_output_identity_mismatch',dict(kind=kind,part=part))
        return validate_payload(kind,saved.get('payload'),prose,part)
    story=copy.deepcopy(prose)
    package=read('seo')
    if set(package)!=set(('title','description','tags')):
        raise StoryValidationError('planning_payload_invalid',dict(kind='seo'))
    story.update(package)
    thumbnail=read('thumbnail')
    if set(thumbnail)!=THUMBNAIL_FIELDS:
        raise StoryValidationError('planning_payload_invalid',dict(kind='thumbnail'))
    story.update(thumbnail)
    visuals={}
    for part in range(visual_worker_count(prose)):
        payload=read('visual',part)
        if set(payload)!={str(i) for i in visual_indices(prose,part)}:
            raise StoryValidationError('planning_visual_coverage',dict(part=part))
        visuals.update(payload)
    install_visuals(story,visuals)
    # No worker can replace scenes/lyrics. The full manifest is validated before saving.
    validate_story(story)
    save_json(root/'story.json',story)
    save_json(root/'planning-join.json',dict(prose_identity=identity,workers=visual_worker_count(prose)+2,scenes=len(visuals),verified=True))
    return story
