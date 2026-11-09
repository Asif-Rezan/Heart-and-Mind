"""Original story-grounded public metadata from the existing local Qwen model."""
import copy
import hashlib
from pathlib import Path
import json
from jsonschema import Draft202012Validator, ValidationError

VERSION = 'hindi-episode-seo-packaging-v1-opening-thumbnail'
# Titles that imitate other channels' songs attract viewers who expect that song.
LOOKALIKE_TITLES = ('dodi dodi','duri duri','duty duty','dum dum','डोडी डोडी','डुरी डुरी','ड्यूटी ड्यूटी','डम डम')


def metadata_schema():
    return {'type':'object','additionalProperties':False,'required':['title','description','tags'],
        'properties':{'title':{'type':'string','minLength':10,'maxLength':100},
                      'description':{'type':'string','minLength':80,'maxLength':1800},
                      'tags':{'type':'array','minItems':5,'maxItems':15,'uniqueItems':True,
                              'items':{'type':'string','minLength':2,'maxLength':40}}}}


def candidate_scenes(song):
    count=len(song['scenes'])
    indexes=set(range(min(8,count)))
    if count>8:
        indexes.update(8+i*(count-9)//15 for i in range(16))
    return [song['scenes'][i] for i in sorted(indexes)]


def thumbnail_scenes(song):
    # Verse-chorus episodes open on the thumbnail scene, so the first frames match the click.
    if song.get('song_form'):
        return [0]
    return [s['index'] for s in candidate_scenes(song)]


def chapter_text(song):
    """Real YouTube chapters from the storyboard sections (each at least 20 seconds)."""
    rows,verse=[],0
    scenes=song.get('scenes',[])
    for i,scene in enumerate(scenes):
        section=scene.get('section')
        if not section or (i and scenes[i-1].get('section')==section):
            continue
        if section=='verse':
            verse+=1
            words=' '.join(scene['lyric'].split()[:6]).rstrip('.!?')
            rows.append(f"{scene['start']//60}:{scene['start']%60:02d} अंतरा {verse}: {words[:1].upper()+words[1:]}")
        elif not rows:
            hook=song.get('hook') or 'Dudi Dudi Dam Dam'
            rows.append('0:00 '+hook[:1].upper()+hook[1:].rstrip('.!?')+' नाच का मुखड़ा')
    return '\n'.join(rows) if len(rows)>=3 else ''


def add_chapters(package, song):
    chapters=chapter_text(song)
    video=package.get('video')
    if not chapters or not isinstance(video,dict) or not isinstance(video.get('description'),str):
        return package
    if chapters in video['description']:
        return package
    room=1800-len(chapters)-2
    body=video['description'][:room].rstrip()
    video['description']=body+'\n\n'+chapters
    return package


def schema(song):
    return {'type':'object','additionalProperties':False,
        'required':['title_candidates','video','shorts','thumbnail'],
        'properties':{
            'title_candidates':{'type':'array','minItems':3,'maxItems':3,'uniqueItems':True,
                                'items':{'type':'string','minLength':10,'maxLength':100}},
            'video':metadata_schema(),'shorts':metadata_schema(),
            'thumbnail':{'type':'object','additionalProperties':False,'required':['scene_index','focus'],
                         'properties':{'scene_index':{'type':'integer','enum':thumbnail_scenes(song)},
                                       'focus':{'type':'string','minLength':15,'maxLength':180}}}}}


def source_identity(song):
    return hashlib.sha256(json.dumps({k:song.get(k) for k in
        ('title','description','lyrics','story_summary','visual_identity','scenes','duration','language')},
        sort_keys=True).encode()).hexdigest()


def validate_package(package, song):
    content={k:package[k] for k in ('title_candidates','video','shorts','thumbnail')}
    Draft202012Validator(schema(song)).validate(content)
    if package.get('version') != VERSION or package.get('source_sha256') != source_identity(song):
        raise ValueError('Episode packaging source/version mismatch')
    if content['video']['title'] not in content['title_candidates']:
        raise ValueError('Selected title must be one of the episode candidates')
    for kind in ('video','shorts'):
        tags=content[kind]['tags']
        if len({tag.strip().casefold() for tag in tags})!=len(tags) or sum(len(t)+2 for t in tags)>450:
            raise ValueError('Episode tags must be unique and fit the upload budget')
    if song.get('language') == 'hi':
        from hindi import validate_generated_text
        validate_generated_text(package)
    return package


TAG_BUDGET = 450


def lookalike(title):
    return isinstance(title,str) and any(word in title.casefold() for word in LOOKALIKE_TITLES)


def repair_package(package, recent=()):
    """Fix deterministic slips locally instead of re-asking the model.

    Only reorders or drops model-written values; never invents public text.
    """
    for kind in ('video','shorts'):
        meta=package.get(kind)
        if not isinstance(meta,dict) or not isinstance(meta.get('tags'),list):
            continue
        seen,tags,used=set(),[],0
        for tag in meta['tags']:
            if not isinstance(tag,str):
                continue
            tag=' '.join(tag.split())
            key=tag.casefold()
            if not tag or key in seen or used+len(tag)+2>TAG_BUDGET:
                continue
            seen.add(key);tags.append(tag);used+=len(tag)+2
        meta['tags']=tags
    candidates=package.get('title_candidates')
    video=package.get('video')
    if isinstance(candidates,list) and isinstance(video,dict):
        title=video.get('title')
        if title not in candidates or title in recent or lookalike(title):
            fresh=[c for c in candidates if isinstance(c,str) and c not in recent and not lookalike(c)]
            if fresh:
                video['title']=fresh[0]
    return package


def packaging_issue(error):
    """Safe diagnostic: locally authored messages, or schema location only."""
    if isinstance(error,ValidationError):
        return {'constraint':error.validator,'path':[str(p) for p in error.absolute_path]}
    if isinstance(error,KeyError):
        return {'constraint':'missing_field'}
    return {'constraint':'semantic','reason':str(error)}


def package_facts(song):
    """Keep all unique verse lyrics; supply opening actions once for Shorts/thumbnail."""
    from rhyme_writer import chorus_line, CHORUS
    chorus=song.get('chorus') or list(CHORUS)
    return dict(title=song['title'], story_summary=song.get('story_summary',''),
        characters=song.get('visual_identity',{}), duration=song['duration'], chorus=chorus,
        verse_lyrics=list(dict.fromkeys(s['lyric'] for s in song['scenes']
                                       if not chorus_line(s['lyric'],chorus))),
        opening=[dict(index=s['index'],lyric=s['lyric'],
                      action=s.get('visual_action',s['prompt'])[:120]) for s in song['scenes'][:8]])


def field_specs(song):
    spec=schema(song)['properties']
    fields={'title_candidates':spec['title_candidates']}
    for group in ('video','shorts','thumbnail'):
        fields.update({group+'.'+key:value for key,value in spec[group]['properties'].items()})
    return fields


def get_field(value,path):
    for key in path.split('.'):
        value=value[key]
    return value


def set_field(value,path,text):
    keys=path.split('.')
    for key in keys[:-1]:
        value=value[key]
    value[keys[-1]]=text


def package_problems(package,song,recent):
    """Return field paths, never discard accepted fields for another field's failure."""
    specs=field_specs(song)
    problems={}
    for path,spec in specs.items():
        try:
            value=get_field(package,path)
        except (KeyError,TypeError):
            problems[path]='missing field'
            continue
        errors=list(Draft202012Validator(spec).iter_errors(value))
        if errors:
            problems[path]='schema: '+', '.join(sorted({str(e.validator) for e in errors}))
            continue
        if song.get('language')=='hi' and (path=='title_candidates' or path in
                ('video.title','video.description','shorts.title','shorts.description')):
            from hindi import require_hindi
            try:
                for text in value if isinstance(value,list) else [value]:
                    require_hindi(text,path)
            except ValueError:
                problems[path]='Use Hindi Devanagari only; only Heart and Mind and #Shorts may use Latin letters.'
    if not any(key in problems for key in ('title_candidates','video.title')):
        candidates=package['title_candidates']
        if not any(c not in recent and not lookalike(c) for c in candidates):
            problems['title_candidates']='Write fresh titles without recent titles or other channels song names.'
    for kind in ('video','shorts'):
        try:
            if lookalike(package[kind]['title']):
                problems[kind+'.title']='Do not imitate another channel song name.'
        except (KeyError,TypeError):
            pass
    return problems


def initial_schema(song):
    # Content bounds are checked below, after preserving the complete response.
    # Structural grammar stays constrained; one overlong field must not cause a
    # full-package retry inside the low-level model wrapper.
    value=copy.deepcopy(schema(song))
    def loosen(node):
        if isinstance(node,dict):
            for key in ('minLength','maxLength','uniqueItems'):
                node.pop(key,None)
            for child in node.values(): loosen(child)
        elif isinstance(node,list):
            for child in node: loosen(child)
    loosen(value)
    return value


def generate_package(song, history=(), seed_offset=0, draft_path=None):
    from rhyme_writer import request_json
    from lyrics_cpu import StoryGenerationError
    identity=source_identity(song)
    facts=package_facts(song)
    recent={h.get('public_title',h.get('title','')) for h in history}
    base=(int(identity[:8],16)+seed_offset*104729) % (2**31-10000)
    path=Path(draft_path) if draft_path else None
    result=None
    if path and path.exists():
        saved=json.loads(path.read_text())
        if saved.get('identity')==identity and saved.get('version')==VERSION:
            result=saved.get('candidate')
    def save():
        if path:
            path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(dict(identity=identity,version=VERSION,candidate=result),ensure_ascii=False,indent=2))
            temp.replace(path)
    if result is None:
        prompt=(
            'Create truthful YouTube metadata for this original Hindi kids rhyme. '
            'All public titles, descriptions and title candidates MUST use Hindi Devanagari, including hashtags and AI disclosure. '
            'Only the proper brand Heart and Mind and optional #Shorts may use Latin letters. '
            'No invented animals, events, educational guarantees, celebrity brands, stock song names, subscribe requests or popularity claims. '
            'Create 3 distinct 45-70 character title_candidates based on the actual animal/action, e.g. नन्हे खरगोश का नाच | हिंदी बालगीत. '
            'video.title must exactly equal one candidate. Descriptions: 2-4 short Hindi sentences, main search phrase near the start, '
            'real story/action, Hindi disclosure that music/illustrations are AI-made, exactly 3 relevant Hindi hashtags. '
            'Do not add timestamps; real chapters are appended locally. Tags: 8-12 distinct relevant phrases, each <=40 characters, total <450. '
            'Shorts title/description/tags describe ONLY opening scenes 0-7 (first 40 seconds), never later events. '
            'Thumbnail scene_index must be an allowed schema value. focus must be ENGLISH, 60-120 characters, hard maximum 180: '
            'describe existing opening faces, emotion, prop/action; same cute pastel 3D cast/setting, no text, no new props or characters. '
            'Avoid recent titles: '+json.dumps([h.get('public_title',h.get('title','')) for h in history[-20:]],ensure_ascii=False)+
            '\nEpisode facts: '+json.dumps(facts,ensure_ascii=False,separators=(',',':')))
        result=request_json(initial_schema(song),prompt,base,budget=2200,validate_text=False)
        save()
    specs=field_specs(song)
    for attempt in range(4):
        repair_package(result,recent)
        problems=package_problems(result,song,recent)
        if not problems:
            result.update(version=VERSION,source_sha256=identity)
            validate_package(result,song)
            add_chapters(result,song)
            save()
            return result
        save()
        print(json.dumps({'check':'episode packaging field repair','attempt':attempt+1,
                          'fields':sorted(problems),'constraints':problems}),flush=True)
        if attempt==3:
            break
        keys=list(problems)
        # Field-only repairs do not resend the original package or full storyboard.
        if all(k.startswith('thumbnail.') for k in keys):
            context={'characters':facts['characters'],'opening':facts['opening'][:1]}
        elif all(k.startswith('shorts.') for k in keys):
            context={'characters':facts['characters'],'opening':facts['opening']}
        else:
            context={k:v for k,v in facts.items() if k!='opening'}
            if any(k.startswith(('shorts.','thumbnail.')) for k in keys):
                context['opening']=facts['opening']
        repair_schema={'type':'object','additionalProperties':False,'required':keys,
                       'properties':{k:specs[k] for k in keys}}
        prompt=('Repair ONLY the named metadata fields; retain the real cast/story. '
            'Public text must be natural Hindi Devanagari, including hashtags and AI disclosure; only Heart and Mind and #Shorts may use Latin. '
            'thumbnail.focus must be English, 60-120 characters, never over 180; no invented props or cast. '
            'For Shorts use only supplied opening scenes (first 40 seconds). Return keys exactly as requested. '
            'Constraints: '+json.dumps(problems,ensure_ascii=False)+
            '\nRejected fields: '+json.dumps({k:get_field(result,k) for k in keys},ensure_ascii=False)+
            '\nRelevant facts: '+json.dumps(context,ensure_ascii=False,separators=(',',':')))
        patched=request_json(repair_schema,prompt,base+attempt+1,
                             budget=min(2200,400+400*len(keys)),validate_text=False)
        for key in keys:
            set_field(result,key,patched[key])
        save()
    raise StoryGenerationError('Episode packaging field repair exhausted; accepted metadata and lyrics retained',
                               code='episode_packaging',retryable=True)


def public_metadata(song, kind='video'):
    """New episodes use their saved package; old unpublished artifacts use their story."""
    if kind not in ('video','shorts'):
        raise ValueError('Unknown upload format')
    if song.get('public_metadata_version') == VERSION:
        return {key:song[key] for key in ('title','description','tags')}
    package=song.get('packaging')
    if package:
        validate_package(package,song)
        return dict(package[kind],tags=list(package[kind]['tags']))
    # Recovery compatibility: never revert an old prepared song to shared fixed text.
    from kids_rhymes import metadata_tags, upload_description
    return dict(title=song['title'],description=upload_description(song),tags=metadata_tags(song))
