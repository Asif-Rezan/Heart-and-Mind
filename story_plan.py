"""Checkpointed outline, independent chapter workers, then one validated reservation."""
import hashlib
import json
from pathlib import Path
from story_writer import (ask, OUTLINE, CHAPTER, VERSION, VOICES, save_json,
                          validate_story, novelty_reason, text_hash, StoryValidationError)

CHAPTERS=6


def outline_identity(draft):
    return hashlib.sha256(json.dumps(draft['outline'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def prepare_outline(root, run_id, history):
    root=Path(root)
    if (root/'story.json').exists():
        story=validate_story(json.loads((root/'story.json').read_text()))
        if story['run_id']!=run_id:
            raise StoryValidationError('story_identity_mismatch')
        return
    path=root/'story-draft.json'
    draft=json.loads(path.read_text()) if path.exists() else {}
    if draft.get('run_id',run_id)!=run_id:
        raise StoryValidationError('draft_identity_mismatch')
    if 'outline' not in draft:
        recent=[dict(title=h['title'],summary=h.get('summary','')) for h in history if h.get('run')!=run_id][-20:]
        seed=int(hashlib.sha256(run_id.encode()).hexdigest()[:7],16)
        outline=ask(OUTLINE,
            'Create an ORIGINAL 8-12 minute Hindi emotional motivational story for Heart and Mind. '
            'Credible everyday Indian family, work or study conflict; meaningful choice; earned hopeful ending. '
            'No instant riches, copied plots, sermons or nursery rhymes. Male narrator and at most one male '
            'and one female dialogue character. All characters retain fixed names, relationships and appearance. '
            'Hindi Devanagari title/description. English planning prose: summary about 350 characters, '
            'character descriptions about 220 characters, world about 140 characters. '
            'Plan exactly SIX chronological chapter beats (about 120 characters each): beginning, struggle, '
            'setback, turning point, constructive action, resolution. Each beat must specify concrete actions '
            'and a distinct start/end so separate writers can continue the same plot without contradictions. '
            'Each chapter will have eight scenes, 24-30 Hindi words per scene. Pastel cute 3D storybook world. '
            'Avoid previous titles and plots: '+json.dumps(recent,ensure_ascii=False),
            seed,2800,checkpoint=root/'outline-response.json')
        draft=dict(run_id=run_id,version=VERSION,outline=outline,chapters=[])
    else:
        draft['run_id']=run_id
    save_json(path,draft)


def chapter_path(root, index):
    if type(index) is not int or not 0<=index<CHAPTERS:
        raise StoryValidationError('invalid_chapter_index')
    return Path(root)/'chapters'/f'chapter-{index}.json'


def chapter_issues(data):
    scenes=data.get('scenes',[]) if isinstance(data,dict) else []
    if not isinstance(scenes,list):
        return dict(scene_schema='expected_array')
    if len(scenes)!=8:
        return dict(scene_count=len(scenes))
    malformed=[i+1 for i,s in enumerate(scenes) if not isinstance(s,dict) or
        not isinstance(s.get('text'),str) or s.get('speaker') not in VOICES or
        not isinstance(s.get('visual'),str) or not 20<=len(s['visual'])<=360]
    if malformed:
        return dict(invalid_schema_scenes=malformed)
    words=[len(s['text'].split()) for s in scenes]
    bad=[]
    for i,scene in enumerate(scenes):
        letters=[c for c in scene['text'] if c.isalpha()]
        if (not 23<=words[i]<=31 or not letters or
            sum('\u0900'<=c<='\u097f' for c in letters)/len(letters)<.9):
            bad.append(i+1)
    narrator_count=sum(s['speaker']=='narrator' for s in scenes)
    return dict(words=words,bad_scenes=bad,narrator_count=narrator_count) if bad or narrator_count!=6 else None


def write_chapter(root,run_id,index):
    root=Path(root)
    path=chapter_path(root,index)
    if (root/'story.json').exists():
        # Reserved/finished identities resume exactly, without calling the model.
        story=validate_story(json.loads((root/'story.json').read_text()))
        if story['run_id']!=run_id:
            raise StoryValidationError('story_identity_mismatch')
        return
    draft=json.loads((root/'story-draft.json').read_text())
    if draft.get('run_id',run_id)!=run_id:
        raise StoryValidationError('draft_identity_mismatch')
    identity=outline_identity(draft)
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved.get('outline_hash')==identity and not chapter_issues(saved):
        return
    outline=draft['outline']
    seed=int(hashlib.sha256((run_id+':chapter:'+str(index)).encode()).hexdigest()[:7],16)
    feedback=''
    for attempt in range(4):
        data=ask(CHAPTER,
            'Write ONLY chapter '+str(index+1)+' of this fixed canonical story: '+json.dumps(outline,ensure_ascii=False)+
            '\nThis chapter beat: '+outline['chapters'][index]+
            '\nUse precisely EIGHT scenes, SIX narrator scenes and TWO character dialogue scenes (male/female). '
            'Use 24-30 space-separated Hindi Devanagari words in every spoken text. Natural full sentences, '
            'no speaker names or stage directions in spoken text. Do not retell prior chapter beats or resolve '
            'events assigned to later chapters. Preserve names/relationships/props in the canonical outline. '
            'The final chapter resolves the conflict through action. Each English visual must describe this '
            'scene action/character/setting, about 120 characters. '+feedback,
            seed+attempt*10,4000,checkpoint=root/'chapters'/f'raw-{index}.json')
        issues=chapter_issues(data)
        if not issues:
            save_json(path,dict(data,outline_hash=identity,index=index))
            print(json.dumps({'phase':'Hindi chapter ready','chapter':index+1,'chapters':CHAPTERS}),flush=True)
            return
        save_json(root/'chapters'/f'validation-{index}.json',dict(attempt=attempt+1,**issues))
        print(json.dumps({'phase':'Hindi chapter repair','chapter':index+1,'attempt':attempt+1,**issues}),flush=True)
        feedback='Previous validation failed: '+json.dumps(issues)+'. Correct these counts/language; never pad or truncate speech.'
    raise StoryValidationError('chapter_validation_failed',dict(chapter=index+1,**issues))


def assemble_story(root,run_id,history):
    root=Path(root)
    manifest=root/'story.json'
    if manifest.exists():
        story=validate_story(json.loads(manifest.read_text()))
        if story['run_id']!=run_id:
            raise StoryValidationError('story_identity_mismatch')
        return story
    draft=json.loads((root/'story-draft.json').read_text())
    if draft.get('run_id',run_id)!=run_id:
        raise StoryValidationError('draft_identity_mismatch')
    identity=outline_identity(draft)
    scenes=[]
    for i in range(CHAPTERS):
        path=chapter_path(root,i)
        if not path.exists():
            raise StoryValidationError('missing_chapter',dict(chapter=i+1))
        data=json.loads(path.read_text())
        if data.get('outline_hash')!=identity or chapter_issues(data):
            raise StoryValidationError('invalid_chapter_checkpoint',dict(chapter=i+1))
        for scene in data['scenes']:
            scenes.append(dict(scene,index=len(scenes)))
    outline=draft['outline']
    story=dict(content_type='hindi_story',writer_version=VERSION,run_id=run_id,title=outline['title'],
        description=outline['description']+'\n\nयह एक मौलिक काल्पनिक कहानी है। आवाज़, चित्र और संगीत AI की सहायता से बनाए गए हैं।\n#HindiStory #MotivationalStory',
        summary=outline['summary'],characters=outline['characters'],world=outline['world'],scenes=scenes,
        lyrics='\n'.join(s['text'] for s in scenes),
        tags=['Hindi motivational story','Hindi emotional story','प्रेरणादायक कहानी','Hindi kahani'])
    validate_story(story)
    others=[h for h in history if h.get('run')!=run_id]
    reason=novelty_reason(story,others)
    if reason:
        raise StoryValidationError('duplicate_story',dict(reason=reason))
    save_json(manifest,story)
    return story
