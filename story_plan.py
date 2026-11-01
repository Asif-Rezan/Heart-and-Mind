"""Checkpointed outline, independent chapter workers, then one validated reservation."""
import copy
import hashlib
import json
from pathlib import Path
from story_writer import (ask, OUTLINE, CHAPTER, VERSION, VOICES, save_json,
                          validate_story, novelty_reason, text_hash, StoryValidationError, object_schema, string, speech_issues, normalize_planning)

from story_engagement import chapter_direction
from story_format import FORMAT, MIN_WORDS, MAX_WORDS

CHAPTERS=6


def outline_identity(draft):
    payload=dict(outline=draft['outline'],format=FORMAT) if draft.get('format')==FORMAT else draft['outline']
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


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
            'Create an ORIGINAL 4-6 minute Hindi emotional motivational story for Heart and Mind. '
            'Credible everyday Indian family, work or study conflict; meaningful choice; earned hopeful ending. '
            'No instant riches, copied plots, sermons or nursery rhymes. One male narrator tells the entire story, including any quoted dialogue. All characters retain fixed names, relationships and appearance. '
            'Hindi Devanagari title/description. English planning prose: summary about 350 characters, '
            'character descriptions about 220 characters: name, exact age, hair, fixed clothing and colors for each person, world about 140 characters. '
            'Plan exactly SIX chronological chapter beats (about 120 characters each): beginning, struggle, '
            'setback, turning point, constructive action, resolution. Each beat must specify concrete actions '
            'and a distinct start/end so separate writers can continue the same plot without contradictions. '
            'Begin with a concrete high-stakes question/action in the first ten seconds, no greeting or intro. '
            'Seed one detail whose significance is paid off at the end. Escalate stakes through choices, '
            'not artificial disasters. Reserve the final two scenes for one story-specific reflective comment '
            'question and a brief optional follow invitation, AFTER the emotional resolution. '
            'Each chapter will have eight scenes, 11-15 Hindi words per scene, about 95-110 words per chapter. Pastel cute 3D storybook world. '
            'Avoid previous titles and plots: '+json.dumps(recent,ensure_ascii=False),
            seed,2800,checkpoint=root/'outline-response.json')
        draft=dict(run_id=run_id,version=VERSION,format=FORMAT,outline=outline,chapters=[])
    else:
        draft['run_id']=run_id
    save_json(path,draft)


def chapter_path(root, index):
    if type(index) is not int or not 0<=index<CHAPTERS:
        raise StoryValidationError('invalid_chapter_index')
    return Path(root)/'chapters'/f'chapter-{index}.json'


DEFAULT_ROLES=('narrator','narrator','male','narrator','narrator','female','narrator','narrator')
REPAIR_REQUESTS=6
REPAIR_VERSION='scene-repair-v3-story-budget'


def scene_issues(scene, expected_speaker=None):
    if (not isinstance(scene,dict) or not isinstance(scene.get('text'),str) or
            scene.get('speaker') not in VOICES or not isinstance(scene.get('visual'),str)):
        return ['schema']
    issues=[]
    if expected_speaker is not None and scene['speaker']!=expected_speaker:
        issues.append('speaker')
    issues.extend(speech_issues(scene['text']))
    if not 20<=len(scene['visual'])<=360:
        issues.append('visual')
    return issues


def chapter_issues(data):
    scenes=data.get('scenes',[]) if isinstance(data,dict) else []
    if not isinstance(scenes,list) or len(scenes)!=8:
        return dict(scene_count=len(scenes) if isinstance(scenes,list) else 0)
    words=[len(s.get('text','').split()) if isinstance(s,dict) else 0 for s in scenes]
    bad=[i+1 for i,s in enumerate(scenes) if scene_issues(s)]
    narrator_count=sum(isinstance(s,dict) and s.get('speaker')=='narrator' for s in scenes)
    total=sum(words)
    if bad or narrator_count not in (6,8):
        return dict(words=words,bad_scenes=bad,narrator_count=narrator_count,total_words=total)
    return None


def scene_schema(indices):
    # Speakers/scene positions are author-controlled before writing. The model
    # only supplies prose for required named slots, so it cannot miscount roles.
    return object_schema({f'scene_{i}':object_schema({'text':dict(string(1,400),description='Spoken narration in Hindi Devanagari only; never English.'),'visual':string(20,360)})
                          for i in indices})


def recovered_roles(rows):
    if len(rows)!=8:
        return list(DEFAULT_ROLES)
    if sum(isinstance(s,dict) and s.get('speaker')=='narrator' for s in rows)==6 and all(
            isinstance(s,dict) and s.get('speaker') in VOICES for s in rows):
        return [s['speaker'] for s in rows]
    # Keep two existing dialogue slots where possible, prioritizing valid prose.
    # Rejected dialogue is rewritten AS narration, never silently relabeled.
    dialogues=[i for i,s in enumerate(rows) if isinstance(s,dict) and s.get('speaker') in ('male','female')]
    if len(dialogues)<2:
        return list(DEFAULT_ROLES)
    chosen=sorted(dialogues,key=lambda i:(bool(scene_issues(rows[i])),i))[:2]
    return [rows[i]['speaker'] if i in chosen else 'narrator' for i in range(8)]


def repair_indices(accepted):
    # Chapter boundaries describe plot beats, not equal-length audio segments.
    # Only repair invalid/missing prose here. The complete 48-scene story owns
    # the word budget; actual synthesized audio owns the duration constraint.
    return [i for i in range(8) if str(i) not in accepted]


def write_chapter(root,run_id,index):
    root=Path(root)
    path=chapter_path(root,index)
    if (root/'story.json').exists():
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
    progress_path=root/'chapters'/f'progress-{index}.json'
    progress=json.loads(progress_path.read_text()) if progress_path.exists() else {}
    if progress and (progress.get('outline_hash')!=identity or progress.get('run_id')!=run_id):
        raise StoryValidationError('chapter_progress_identity_mismatch',dict(chapter=index+1))
    if not progress:
        raw_path=root/'chapters'/f'raw-{index}.json'
        raw=json.loads(raw_path.read_text()) if raw_path.exists() else {}
        rows=raw.get('scenes',[]) if isinstance(raw,dict) else []
        if not isinstance(rows,list) or len(rows)!=8:
            rows=[]
        roles=['narrator']*8 if draft.get('format')==FORMAT else recovered_roles(rows)
        accepted={str(i):copy.deepcopy(s) for i,s in enumerate(rows) if not scene_issues(s,roles[i])}
        progress=dict(version=REPAIR_VERSION,run_id=run_id,outline_hash=identity,index=index,
                      roles=roles,accepted=accepted,drafts={str(i):s for i,s in enumerate(rows)},requests=0)
    roles=progress.get('roles',[])
    if len(roles)!=8 or roles.count('narrator')!=(8 if draft.get('format')==FORMAT else 6) or any(role not in VOICES for role in roles):
        raise StoryValidationError('invalid_chapter_role_plan',dict(chapter=index+1))
    accepted={key:value for key,value in progress['accepted'].items() if key in {str(i) for i in range(8)}
              and not scene_issues(value,roles[int(key)])}
    progress['accepted']=accepted
    for raw_path in sorted((root/'chapters').glob(f'raw-attempt-*-{index}.json'),
                           key=lambda path:int(path.name.split('-')[-2])):
        raw=json.loads(raw_path.read_text())
        if not isinstance(raw,dict):
            continue
        for i in range(8):
            if str(i) in accepted or f'scene_{i}' not in raw:
                continue
            value=raw[f'scene_{i}']
            if not isinstance(value,dict) or not all(isinstance(value.get(k),str) for k in ('text','visual')):
                continue
            candidate=dict(value,speaker=roles[i])
            candidate=normalize_planning({'scene':candidate},
                object_schema({'scene':object_schema({'speaker':{'type':'string'},
                    'text':dict(string(1,400),description='Spoken narration in Hindi Devanagari only; never English.'),'visual':string(20,360)})}))['scene']
            progress['drafts'][str(i)]=candidate
            if not scene_issues(candidate,roles[i]):
                accepted[str(i)]=candidate
    save_json(progress_path,progress)
    outline=draft['outline']
    seed=int(hashlib.sha256((run_id+':chapter:'+str(index)).encode()).hexdigest()[:7],16)
    language_attempts={}  # Fresh bounded budget per explicit recovery; accepted prose persists.
    for attempt in range(REPAIR_REQUESTS):
        pending=repair_indices(accepted)
        if not pending:
            break
        request_number=progress['requests']
        progress['requests']+=1
        save_json(progress_path,progress)  # Resume with new seeds after interruption.
        context=[dict(scene=i+1,speaker=roles[i],**{k:v for k,v in progress.get('drafts',{}).get(str(i),{}).items()
                                                 if k in ('text','visual')}) for i in range(8)]
        targets={f'scene_{i}':dict(position=i+1,speaker=roles[i],
                    instruction='narration in third person' if roles[i]=='narrator' else 'direct character dialogue')
                 for i in pending}
        translation=[i for i in pending if speech_issues(progress.get('drafts',{}).get(str(i),{}).get('text'))==['hindi']
                     and not scene_issues(dict(progress['drafts'][str(i)],text='यह कहानी आगे बढ़ती है।'),roles[i])]
        if translation:
            pending=translation[:4]
            attempts=language_attempts
            progress['language_attempts']=attempts
            exhausted=[i+1 for i in pending if attempts.get(str(i),0)>=2]
            if exhausted:
                raise StoryValidationError('chapter_language_repair_incomplete',dict(chapter=index+1,
                    pending_scenes=exhausted,expected_language='Hindi Devanagari',attempt_limit=2))
            for i in pending:attempts[str(i)]=attempts.get(str(i),0)+1
            save_json(progress_path,progress)
            schema=object_schema({f'scene_{i}':object_schema({'text':dict(string(1,400),
                description='Hindi Devanagari spoken narration only, never English or Romanized Hindi.')}) for i in pending})
            prompt=('The previous text was rejected because it was ENGLISH, not Hindi. '
                'Translate ONLY the selected text fields into natural spoken Hindi Devanagari. '
                'Preserve the same meaning, actions, chronology and canonical names; do not invent events. '
                'Do not return visual fields or rewrite accepted scenes. Aim 11-18 Hindi words per text. '
                'Example: Arjun opens the door -> अर्जुन दरवाजा खोलता है। '
                'Source texts: '+json.dumps({f'scene_{i}':progress['drafts'][str(i)]['text'] for i in pending},ensure_ascii=False))
        else:
            schema=scene_schema(pending)
            prompt=(
            'Write or repair ONLY the requested scene slots for chapter '+str(index+1)+'. '
            'Canonical outline: '+json.dumps(outline,ensure_ascii=False)+
            '\nThis chapter beat: '+outline['chapters'][index]+
            '\nEngagement direction: '+chapter_direction(index)+
            '\nFixed scene context: '+json.dumps(context,ensure_ascii=False)+
            '\nRequested slots/roles: '+json.dumps(targets,ensure_ascii=False)+
            '\nReturn exactly the required scene_N JSON keys. Each text is natural Hindi Devanagari, '+
            ('aim 11-15 space-separated words, about 100 words total per chapter. ' if draft.get('format')==FORMAT else 'aim 26-30 words for narration, 12-24 for dialogue. ')+
            'Use the assigned speaker role BEFORE writing: narrator tells events, male/female is direct dialogue '
            'by an established character. Each visual is English, about 120 characters: name the canonical person, exact visible action, story prop and current location from THIS text. No abstract mood-only pictures or unrelated scenery. Repeat the exact established clothing and age when visible. No speaker labels, stage directions, repeated filler or word padding. '
            'Preserve the scene meaning and canonical names. Do not narrate a line and then repeat it as dialogue. '
            'allowing individual plot beats to vary naturally in length. '
            'Leave all unrequested scenes alone; do not retell earlier beats or resolve later chapters.')
        from lyrics_cpu import StoryGenerationError
        from jsonschema import ValidationError
        try:
            response=ask(schema,prompt,(seed+request_number*17)%(2**31-3),min(4000,500+400*len(pending)),
                checkpoint=root/'chapters'/f'raw-attempt-{request_number}-{index}.json')
        except (StoryGenerationError,ValidationError,json.JSONDecodeError) as error:
            if isinstance(error,StoryGenerationError) and error.code!='story_model_response_invalid':
                raise StoryValidationError('chapter_model_runtime_failure',dict(chapter=index+1,model_code=error.code)) from None
            print(json.dumps(dict(phase='chapter model response retry',chapter=index+1,request=request_number+1,
                                  error_type=type(error).__name__,pending_scenes=[i+1 for i in pending])),flush=True)
            if attempt==REPAIR_REQUESTS-1:
                raise StoryValidationError('chapter_model_response_invalid',dict(chapter=index+1,
                    error_type=type(error).__name__,pending_scenes=[i+1 for i in pending])) from None
            continue
        rejected={}
        for i in pending:
            value=response.get(f'scene_{i}',{})
            candidate=dict(progress['drafts'][str(i)],text=value.get('text')) if translation else dict(value,speaker=roles[i])
            issues=scene_issues(candidate,roles[i])
            progress['drafts'][str(i)]=candidate
            if not issues:
                accepted[str(i)]=candidate
                progress['drafts'][str(i)]=candidate
            else:
                rejected[str(i+1)]=dict(issues=issues,words=len(candidate.get('text','').split()))
            save_json(progress_path,progress)
        remaining=repair_indices(accepted)
        diagnostics=dict(chapter=index+1,request=request_number+1,accepted_scenes=len(accepted),
                         pending_scenes=[i+1 for i in remaining],rejected=rejected)
        save_json(root/'chapters'/f'validation-{index}.json',diagnostics)
        print(json.dumps(dict(phase='Hindi scene repair',**diagnostics)),flush=True)
    data=dict(scenes=[accepted[str(i)] for i in range(8)]) if len(accepted)==8 else {}
    issues=chapter_issues(data)
    if issues:
        code='chapter_language_repair_incomplete' if any(speech_issues(progress['drafts'].get(str(i),{}).get('text'))==['hindi'] for i in repair_indices(accepted)) else 'chapter_scene_repair_incomplete'
        raise StoryValidationError(code,dict(chapter=index+1,
            accepted_scenes=len(accepted),pending_scenes=[i+1 for i in repair_indices(accepted)],**issues))
    save_json(path,dict(data,outline_hash=identity,index=index,repair_version=REPAIR_VERSION))
    print(json.dumps({'phase':'Hindi chapter ready','chapter':index+1,'chapters':CHAPTERS}),flush=True)


def repair_story_budget(root, run_id, draft, chapters):
    """Repair prose in place; keep canonical identities and checkpoint each gain."""
    from jsonschema import ValidationError
    from lyrics_cpu import StoryGenerationError

    minimum, maximum = (MIN_WORDS, MAX_WORDS) if draft.get('format')==FORMAT else (1000,1600)
    target_words = 14 if draft.get('format')==FORMAT else 27

    def distance(total):
        return max(minimum-total, total-maximum, 0)

    scenes=[scene for chapter in chapters for scene in chapter['scenes']]
    total=sum(len(scene['text'].split()) for scene in scenes)
    if not distance(total):
        return
    path=Path(root)/'story-budget-repair.json'
    identity=outline_identity(draft)
    progress=json.loads(path.read_text()) if path.exists() else {}
    if progress and (progress.get('run_id')!=run_id or progress.get('outline_hash')!=identity):
        raise StoryValidationError('story_budget_identity_mismatch')
    request=progress.get('requests',0)
    seed=int(hashlib.sha256((run_id+':budget').encode()).hexdigest()[:7],16)
    tried={i:0 for i in range(len(scenes))}
    for attempt in range(12):
        if not distance(total):
            return
        expanding=total<minimum
        # Rotate failed slots so one uncooperative scene cannot block the rest.
        eligible=[i for i,scene in enumerate(scenes)
                  if (len(scene['text'].split())<target_words if expanding else len(scene['text'].split())>target_words)]
        indices=sorted(eligible,key=lambda i:(tried[i],
            len(scenes[i]['text'].split())*(1 if expanding else -1)))[:8]
        if not indices:
            break
        for i in indices:
            tried[i]+=1
        schema=object_schema({f'scene_{i}':object_schema({'text':string(1,400)}) for i in indices})
        request+=1
        diagnostic=dict(run_id=run_id,outline_hash=identity,requests=request,total_words=total,
                        minimum_words=minimum,maximum_words=maximum,pending=True)
        save_json(path,diagnostic)
        try:
            response=ask(schema,
                'Revise ONLY the requested Hindi scene texts to repair the complete story word budget. '
                f'The complete story currently has {total} words and needs {minimum}-{maximum}. '
                +('Expand' if expanding else 'Condense')+
                f' each requested text to {target_words-1}-{target_words+1} space-separated Hindi words, at most 400 characters. '
                'Preserve actions, names, chronology and assigned speaker. No filler, repetition, '
                'new plot events or stage directions. Return exactly the requested scene_N text objects. '
                'Canonical outline: '+json.dumps(draft['outline'],ensure_ascii=False)+
                '\nRequested scenes with surrounding context: '+json.dumps({f'scene_{i}':
                    scenes[max(0,i-1):min(len(scenes),i+2)] for i in indices},ensure_ascii=False),
                (seed+request*17)%(2**31-3),min(4000,500+400*len(indices)),
                checkpoint=Path(root)/'budget-responses'/f'request-{request}.json')
        except (StoryGenerationError,ValidationError,json.JSONDecodeError) as error:
            diagnostic['error_type']=type(error).__name__
            save_json(path,diagnostic)
            print(json.dumps(dict(phase='story budget retry',**diagnostic)),flush=True)
            continue
        for i in indices:
            value=response.get(f'scene_{i}',{})
            if not isinstance(value,dict):
                continue
            candidate=dict(scenes[i],text=value.get('text'))
            if scene_issues(candidate):
                continue
            proposed=total-len(scenes[i]['text'].split())+len(candidate['text'].split())
            if distance(proposed)>=distance(total):
                continue
            chapters[i//8]['scenes'][i%8]=candidate
            # Persist first: interruption must never lose a successful repair.
            save_json(chapter_path(root,i//8),chapters[i//8])
            scenes[i]=candidate
            total=proposed
        diagnostic.update(total_words=total,pending=bool(distance(total)))
        save_json(path,diagnostic)
        print(json.dumps(dict(phase='story budget repair',**diagnostic)),flush=True)
    if distance(total):
        raise StoryValidationError('story_budget_repair_incomplete',dict(
            total_words=total,minimum_words=minimum,maximum_words=maximum,requests=request))


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
    chapters=[]
    for i in range(CHAPTERS):
        path=chapter_path(root,i)
        if not path.exists():
            raise StoryValidationError('missing_chapter',dict(chapter=i+1))
        data=json.loads(path.read_text())
        if data.get('outline_hash')!=identity or chapter_issues(data):
            raise StoryValidationError('invalid_chapter_checkpoint',dict(chapter=i+1))
        chapters.append(data)
    repair_story_budget(root,run_id,draft,chapters)
    scenes=[]
    for data in chapters:
        for scene in data['scenes']:
            scenes.append(dict(scene,index=len(scenes)))
    outline=draft['outline']
    story=dict(content_type='hindi_story',writer_version=VERSION,run_id=run_id,title=outline['title'],
        description=outline['description']+'\n\nयह एक मौलिक काल्पनिक कहानी है। आवाज़, चित्र और संगीत AI की सहायता से बनाए गए हैं।\n#HindiStory #MotivationalStory',
        summary=outline['summary'],characters=outline['characters'],world=outline['world'],scenes=scenes,
        lyrics='\n'.join(s['text'] for s in scenes),
        tags=['Hindi motivational story','Hindi emotional story','प्रेरणादायक कहानी','Hindi kahani'])
    if draft.get('format')==FORMAT:
        story['format']=FORMAT
        from story_engagement import polish_engagement
        polish_engagement(root,story)
        repair_repetition(root, story)
        from story_packaging import prepare_packaging
        prepare_packaging(root,story)
        prepare_visuals(root, story)
    validate_story(story)
    others=[h for h in history if h.get('run')!=run_id]
    reason=novelty_reason(story,others)
    if reason:
        raise StoryValidationError('duplicate_story',dict(reason=reason))
    save_json(manifest,story)
    return story


def repair_repetition(root, story):
    from story_writer import repeated_scenes
    for attempt in range(3):
        indices = repeated_scenes(story['scenes'])
        if not indices:
            return
        for start in range(0, len(indices), 8):
            slots = indices[start:start+8]
            response = ask(scene_schema(slots),
                'Edit ONLY repeated lines in the requested scenes. Tell each event ONCE, no recap or echo of dialogue. '
                'Write 11-15 Hindi words per scene; preserve the plot and chronological action. '
                'Update each English visual to represent exactly that text with the same named people, clothing, props and location. '
                'Full story: '+json.dumps(story,ensure_ascii=False)+
                '\nRequested scenes: '+json.dumps(slots),
                int(text_hash(story['run_id']+str(attempt)+str(start))[:7],16),
                min(4000,500+400*len(slots)),
                checkpoint=Path(root)/'repetition-responses'/f'{attempt}-{start}.json')
            for i in slots:
                candidate=dict(response[f'scene_{i}'],speaker='narrator',index=i)
                if scene_issues(candidate,'narrator'):
                    raise StoryValidationError('invalid_repetition_repair',dict(scene=i))
                story['scenes'][i]=candidate
            story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
    if repeated_scenes(story['scenes']):
        raise StoryValidationError('repeated_story_lines')


def prepare_visuals(root, story):
    """Review imagery against the final spoken script, after all prose repairs."""
    from story_writer import scene_prompt
    path=Path(root)/'visual-plan.json'
    identity=text_hash(json.dumps(story,sort_keys=True,ensure_ascii=False))
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved and saved.get('identity')!=identity:
        saved={}
    saved.setdefault('identity',identity)
    saved.setdefault('scenes',{})
    for start in range(0,len(story['scenes']),8):
        slots=list(range(start,min(start+8,len(story['scenes']))))
        if all(str(i) in saved['scenes'] for i in slots):
            continue
        schema=object_schema({f'scene_{i}':string(30,360) for i in slots})
        response=ask(schema,
            'Storyboard the FINAL Hindi narration faithfully. For every requested scene return a compact English image prompt. '
            'Show exactly the concrete action, object and location described in that text. No generic unrelated scenery. '
            'Use the canonical age, hair, clothing colors, props and architecture consistently. State visible appearance explicitly, '
            'not just a character name. At most two visible people. Never invent a new character or change clothes. '
            'One action per frame, main person and prop clear, same colorful 3D storybook style. '
            'Keep each prompt under about 60 English words, put action and defining appearance first. '
            'Canonical cast: '+story['characters']+' World: '+story['world']+
            '\nFull chronological story: '+json.dumps(story['scenes'],ensure_ascii=False)+
            '\nRequested indices: '+json.dumps(slots),
            int(identity[:7],16)+start,3500,
            checkpoint=Path(root)/'visual-responses'/f'{start}.json')
        for i in slots:
            saved['scenes'][str(i)]=response[f'scene_{i}']
        save_json(path,saved)
    if 'thumbnail_scene' not in saved or 'thumbnail_prompt' not in saved:
        response=ask(object_schema({'scene':{'type':'integer','minimum':0,'maximum':47},
                                    'thumbnail_prompt':string(80,360)}),
            'Choose the single scene that most truthfully represents this story main conflict or meaningful choice. '
            'Also write a SEPARATE English image-generation prompt designed for a YouTube thumbnail at small mobile size. '
            'This is a fresh composition, not a screenshot. Use the same canonical character appearance and actual '
            'event/prop/setting of the selected scene. One dominant expressive face, one clear story object, '
            'strong subject/background contrast, bright face lighting, bold saturated complementary colors, '
            'uncluttered composition, instantly readable emotional stakes, no tiny details, no text or lettering. '
            'Create curiosity about the real conflict without inventing danger, wealth, tears or plot events. '
            'Put character appearance and the main visual action first; at most 60 words. '
            'No unrelated poster, invented event, or generic sunrise. Canonical cast: '+story['characters']+' World: '+story['world']+' '
            'Title: '+story['title']+' Summary: '+story['summary']+
            '\nScenes: '+json.dumps(story['scenes'],ensure_ascii=False),
            int(identity[:7],16),500,checkpoint=Path(root)/'thumbnail-selection.json')
        saved['thumbnail_scene']=response['scene']
        saved['thumbnail_prompt']=response['thumbnail_prompt']
        save_json(path,saved)
    story['visuals']=saved['scenes']
    story['thumbnail_scene']=saved['thumbnail_scene']
    story['thumbnail_prompt']=saved['thumbnail_prompt']
