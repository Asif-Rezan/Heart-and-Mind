"""Checkpointed outline, independent chapter workers, then one validated reservation."""
import copy
import hashlib
import json
from pathlib import Path
from story_writer import (ask, OUTLINE, CHAPTER, VERSION, VOICES, save_json,
                          validate_story, novelty_reason, text_hash, StoryValidationError, object_schema, string, speech_issues, normalize_planning)

from story_engagement import chapter_direction
from story_format import FORMAT, MIN_WORDS, MAX_WORDS, SAMPLE_FORMAT, is_short, is_sample, scenes_per_chapter, word_bounds

CHAPTERS=6


def outline_identity(draft):
    payload=dict(outline=draft['outline'],format=draft['format']) if is_short(draft) else draft['outline']
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
        import os
        requested_format=os.getenv('STORY_FORMAT',FORMAT)
        if requested_format not in (FORMAT,SAMPLE_FORMAT):raise ValueError('Unsupported story format')
        sample=requested_format==SAMPLE_FORMAT
        duration_text='one-minute' if sample else '4-6 minute'
        chapter_text=('Each chapter has TWO scenes, about 22-26 Hindi words total per chapter; 120-165 words in the whole story. ' if sample else 'Each chapter will have eight scenes with complete spoken Hindi sentences, aim about 110-120 words per chapter without padding. ')
        outline=ask(OUTLINE,
            f'Create an ORIGINAL {duration_text} Hindi emotional motivational story for Heart and Mind. '
            'Credible everyday Indian family, work or study conflict; meaningful choice; earned hopeful ending. '
            'No instant riches, copied plots, sermons or nursery rhymes. One male narrator tells the entire story, including any quoted dialogue. All characters retain fixed names, relationships and appearance. '
            'Hindi Devanagari title/description. English planning prose: summary about 350 characters, '
            'character descriptions about 220 characters: name, exact age, hair, fixed clothing and colors for each person, world about 140 characters. '
            'Plan exactly SIX chronological chapter beats (about 120 characters each): beginning, struggle, '
            'setback, turning point, constructive action, resolution. Each beat must specify concrete actions '
            'and a distinct start/end so separate writers can continue the same plot without contradictions. '
            'Begin with a concrete high-stakes question/action in the first ten seconds, no greeting or intro. '
            'Use a curiosity gap rooted in a specific dilemma so viewers want to learn what happens next. '
            'Show a clear desire, obstacles, a costly setback, a meaningful decision and an earned hopeful payoff. '
            'Make the full story engaging through actions, dialogue and consequences; convey motivation through the story itself. '
            'Seed one detail whose significance is paid off at the end. Escalate stakes through choices, '
            'not artificial disasters. AFTER the emotional resolution, reserve the penultimate scene for a brief friendly '
            'invitation to subscribe to Heart and Mind, and the final scene for one story-specific reflective question '
            'inviting viewers to comment. Keep both natural and short; no pressure, guilt or repeated requests. '
            +chapter_text+'Pastel cute 3D storybook world. '
            'Avoid previous titles and plots: '+json.dumps(recent,ensure_ascii=False),
            seed,2800,checkpoint=root/'outline-response.json')
        draft=dict(run_id=run_id,version=VERSION,format=requested_format,outline=outline,chapters=[])
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


def chapter_issues(data,expected_count=8):
    scenes=data.get('scenes',[]) if isinstance(data,dict) else []
    if not isinstance(scenes,list) or len(scenes)!=expected_count:
        return dict(scene_count=len(scenes) if isinstance(scenes,list) else 0)
    words=[len(s.get('text','').split()) if isinstance(s,dict) else 0 for s in scenes]
    bad=[i+1 for i,s in enumerate(scenes) if scene_issues(s)]
    narrator_count=sum(isinstance(s,dict) and s.get('speaker')=='narrator' for s in scenes)
    total=sum(words)
    if bad or narrator_count not in ((6,8) if expected_count==8 else (expected_count,)):
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


def repair_indices(accepted,count=8):
    # Chapter boundaries describe plot beats, not equal-length audio segments.
    # Only repair invalid/missing prose here. The complete 48-scene story owns
    # the word budget; actual synthesized audio owns the duration constraint.
    return [i for i in range(count) if str(i) not in accepted]


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
    count=scenes_per_chapter(draft)
    identity=outline_identity(draft)
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved.get('outline_hash')==identity and not chapter_issues(saved,count):
        return
    progress_path=root/'chapters'/f'progress-{index}.json'
    progress=json.loads(progress_path.read_text()) if progress_path.exists() else {}
    if progress and (progress.get('outline_hash')!=identity or progress.get('run_id')!=run_id):
        raise StoryValidationError('chapter_progress_identity_mismatch',dict(chapter=index+1))
    if not progress:
        raw_path=root/'chapters'/f'raw-{index}.json'
        raw=json.loads(raw_path.read_text()) if raw_path.exists() else {}
        rows=raw.get('scenes',[]) if isinstance(raw,dict) else []
        if not isinstance(rows,list) or len(rows)!=count:
            rows=[]
        roles=['narrator']*count if is_short(draft) else recovered_roles(rows)
        accepted={str(i):copy.deepcopy(s) for i,s in enumerate(rows) if not scene_issues(s,roles[i])}
        progress=dict(version=REPAIR_VERSION,run_id=run_id,outline_hash=identity,index=index,
                      roles=roles,accepted=accepted,drafts={str(i):s for i,s in enumerate(rows)},requests=0)
    roles=progress.get('roles',[])
    if len(roles)!=count or roles.count('narrator')!=(count if is_short(draft) else 6) or any(role not in VOICES for role in roles):
        raise StoryValidationError('invalid_chapter_role_plan',dict(chapter=index+1))
    accepted={key:value for key,value in progress['accepted'].items() if key in {str(i) for i in range(count)}
              and not scene_issues(value,roles[int(key)])}
    progress['accepted']=accepted
    for raw_path in sorted((root/'chapters').glob(f'raw-attempt-*-{index}.json'),
                           key=lambda path:int(path.name.split('-')[-2])):
        raw=json.loads(raw_path.read_text())
        if not isinstance(raw,dict):
            continue
        for i in range(count):
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
        pending=repair_indices(accepted,count)
        if not pending:
            break
        request_number=progress['requests']
        progress['requests']+=1
        save_json(progress_path,progress)  # Resume with new seeds after interruption.
        context=[dict(scene=i+1,speaker=roles[i],**{k:v for k,v in progress.get('drafts',{}).get(str(i),{}).items()
                                                 if k in ('text','visual')}) for i in range(count)]
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
            ('write TWO scenes, aim 11-13 Hindi words per scene, about 22-26 words in this entire chapter. ' if is_sample(draft) else 'aim about 110-120 words total per chapter, with fluid complete sentences, usually 14-16 words per beat. No filler or forced word padding. ' if is_short(draft) else 'aim 26-30 words for narration, 12-24 for dialogue. ')+
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
        remaining=repair_indices(accepted,count)
        diagnostics=dict(chapter=index+1,request=request_number+1,accepted_scenes=len(accepted),
                         pending_scenes=[i+1 for i in remaining],rejected=rejected)
        save_json(root/'chapters'/f'validation-{index}.json',diagnostics)
        print(json.dumps(dict(phase='Hindi scene repair',**diagnostics)),flush=True)
    data=dict(scenes=[accepted[str(i)] for i in range(count)]) if len(accepted)==count else {}
    issues=chapter_issues(data,count)
    if issues:
        code='chapter_language_repair_incomplete' if any(speech_issues(progress['drafts'].get(str(i),{}).get('text'))==['hindi'] for i in repair_indices(accepted,count)) else 'chapter_scene_repair_incomplete'
        raise StoryValidationError(code,dict(chapter=index+1,
            accepted_scenes=len(accepted),pending_scenes=[i+1 for i in repair_indices(accepted,count)],**issues))
    save_json(path,dict(data,outline_hash=identity,index=index,repair_version=REPAIR_VERSION))
    print(json.dumps({'phase':'Hindi chapter ready','chapter':index+1,'chapters':CHAPTERS}),flush=True)


def repair_story_budget(root, run_id, draft, chapters):
    """Repair prose in place; keep canonical identities and checkpoint each gain."""
    from jsonschema import ValidationError
    from lyrics_cpu import StoryGenerationError

    minimum, maximum = word_bounds(draft)
    count=scenes_per_chapter(draft)
    target_words = 12 if is_sample(draft) else 14 if is_short(draft) else 27

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
            len(scenes[i]['text'].split())*(1 if expanding else -1)))[:2 if is_short(draft) else 8]
        if not indices:
            break
        for i in indices:
            tried[i]+=1
        schema=object_schema({f'scene_{i}':object_schema({'text':string(1,400)}) for i in indices})
        if is_short(draft):
            from story_constraints import hindi_word_pattern
            for spec in schema['properties'].values():
                spec['properties']['text']['pattern']=hindi_word_pattern(target_words-1,target_words+1)
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
                'Canonical plot and cast: '+json.dumps({k:draft['outline'][k] for k in ('summary','characters')},ensure_ascii=False)+
                '\nRequested spoken beats and neighbors: '+json.dumps(scene_context(dict(scenes=scenes),indices),ensure_ascii=False)+
                '\nRequested slots: '+json.dumps(indices),
                (seed+request*17)%(2**31-3),min(4000,500+(200 if is_short(draft) else 400)*len(indices)),
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
            chapters[i//count]['scenes'][i%count]=candidate
            # Persist first: interruption must never lose a successful repair.
            save_json(chapter_path(root,i//count),chapters[i//count])
            scenes[i]=candidate
            total=proposed
        diagnostic.update(total_words=total,pending=bool(distance(total)))
        save_json(path,diagnostic)
        print(json.dumps(dict(phase='story budget repair',**diagnostic)),flush=True)
    if distance(total):
        raise StoryValidationError('story_budget_repair_incomplete',dict(
            total_words=total,minimum_words=minimum,maximum_words=maximum,requests=request))


def assemble_story(root,run_id,history,prose_only=False):
    root=Path(root)
    manifest=root/'story.json'
    if manifest.exists():
        story=validate_story(json.loads(manifest.read_text()))
        if story['run_id']!=run_id:
            raise StoryValidationError('story_identity_mismatch')
        if prose_only:save_json(root/'story-prose.json',story)
        return story
    prose_path=root/'story-prose.json'
    if prose_path.exists():
        story=validate_story(json.loads(prose_path.read_text()),require_planning=False)
        if story['run_id']!=run_id:raise StoryValidationError('story_identity_mismatch')
        reason=novelty_reason(story,[h for h in history if h.get('run')!=run_id])
        if reason:raise StoryValidationError('duplicate_story',dict(reason=reason))
        if prose_only:return story
        if is_short(story):
            from story_packaging import prepare_packaging
            prepare_packaging(root,story)
            prepare_visuals(root,story)
        validate_story(story)
        save_json(manifest,story)
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
        if data.get('outline_hash')!=identity or chapter_issues(data,scenes_per_chapter(draft)):
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
    if is_short(draft):
        story['format']=draft['format']
        from story_engagement import polish_engagement
        polish_engagement(root,story)
        repair_repetition(root, story)
    validate_story(story,require_planning=False)
    reason=novelty_reason(story,[h for h in history if h.get('run')!=run_id])
    if reason:raise StoryValidationError('duplicate_story',dict(reason=reason))
    save_json(root/'story-prose.json',story)
    if prose_only:return story
    if is_short(story):
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


def scene_context(story, indices, neighbors=1):
    """Only the final spoken beats relevant to this request, without 48 visuals."""
    wanted={j for i in indices for j in range(max(0,i-neighbors),min(len(story['scenes']),i+neighbors+1))}
    return [dict(index=i,text=story['scenes'][i]['text']) for i in sorted(wanted)]


def repair_repetition(root, story):
    """Reject echoes, save each accepted repair, and resume only unresolved slots."""
    from story_writer import repeated_scenes, normalized
    from story_engagement import has_closing_cta
    from difflib import SequenceMatcher
    import re
    root=Path(root)
    identity=hashlib.sha256(json.dumps(dict(run_id=story['run_id'],scenes=story['scenes']),
        sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path=root/'repetition-state.json'
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved and identity not in (saved.get('identity'),saved.get('output_identity')):
        raise StoryValidationError('repetition_checkpoint_identity_mismatch')
    if saved:
        story['scenes']=saved['scenes']
        story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
    else:
        saved=dict(identity=identity,output_identity=identity,scenes=story['scenes'],requests=0,rejections={})
    minimum,maximum=word_bounds(story)
    pending=repeated_scenes(story['scenes'])
    if not pending:
        return
    save_json(path,saved)
    # Fixed, bounded batches keep prompts small on CPU. A retry gets explicit
    # rejection feedback rather than silently accepting the original echo.
    for start in range(0,len(pending),2):
        batch=pending[start:start+2]
        for attempt in range(2):
            current=set(repeated_scenes(story['scenes']))
            slots=[i for i in batch if i in current]
            if not slots:
                break
            forbidden={}
            for i in slots:
                lines=[]
                for sentence in re.split(r'[।.!?\n]+',story['scenes'][i]['text']):
                    line=normalized(sentence)
                    if len(line.split())<3:continue
                    for prior in story['scenes'][:i]:
                        for old in re.split(r'[।.!?\n]+',prior['text']):
                            old_line=normalized(old)
                            if line==old_line or (min(len(line.split()),len(old_line.split()))>=10 and
                                SequenceMatcher(None,line,old_line,autojunk=False).ratio()>=.92):
                                lines.append(old)
                forbidden[str(i)]=lines
            saved['requests']+=1
            save_json(path,saved)
            from story_constraints import edit_word_limits,constrain_edits
            limits=edit_word_limits(story,slots)
            response=ask(constrain_edits(scene_schema(slots),limits),
                'REWRITE the requested repeated narration, do not copy or return its current words. '
                'Each later scene must ADVANCE its own chronological beat, not recap an earlier event. '
                'Keep one narrator, established people and canonical events. Write natural Hindi Devanagari, '
                f'roughly the same word count as the original; preserve the complete {minimum}-{maximum} word budget. '
                'English visual must match the new action with fixed appearance. A closing viewer-comment '
                'invitation must remain if editing the final scene. Returning the same line is REJECTED. '
                'Canonical summary: '+story['summary']+' Cast: '+story['characters']+
                '\nFinal neighboring beats: '+json.dumps(scene_context(story,slots),ensure_ascii=False)+
                '\nRequested scenes and current visuals: '+json.dumps([story['scenes'][i] for i in slots],ensure_ascii=False)+
                '\nAlready narrated lines you MUST NOT repeat: '+json.dumps(forbidden,ensure_ascii=False)+
                '\nPer-scene word limits: '+json.dumps(limits)+
                '\nPrevious rejection feedback: '+json.dumps({str(i):saved['rejections'].get(str(i)) for i in slots}),
                int(identity[:7],16)+saved['requests']*17,500+200*len(slots),
                checkpoint=root/'repetition-responses'/f"rewrite-{saved['requests']}.json")
            for i in slots:
                value=response.get(f'scene_{i}',{})
                candidate=dict(value,speaker='narrator',index=i)
                reason=None
                if scene_issues(candidate,'narrator'):reason='invalid_hindi_or_visual'
                elif normalized(candidate['text'])==normalized(story['scenes'][i]['text']):reason='unchanged_echo'
                else:
                    proposed=[dict(s) for s in story['scenes']];proposed[i]=candidate
                    repeats=set(repeated_scenes(proposed))
                    total=sum(len(s['text'].split()) for s in proposed)
                    if i in repeats or not repeats.issubset(current):reason='still_repeated_or_new_echo'
                    elif not minimum<=total<=maximum:reason='story_word_budget'
                    elif i==len(proposed)-1 and has_closing_cta(story['scenes']) and not has_closing_cta(proposed):reason='closing_cta_removed'
                if reason:
                    saved['rejections'][str(i)]=reason
                else:
                    story['scenes'][i]=candidate
                    story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
                    current=set(repeated_scenes(story['scenes']))
                    saved['scenes']=story['scenes']
                    saved['output_identity']=hashlib.sha256(json.dumps(dict(run_id=story['run_id'],scenes=story['scenes']),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    saved['rejections'].pop(str(i),None)
                    print(json.dumps(dict(phase='repetition repair saved',scene=i,pending_scenes=sorted(current))),flush=True)
                save_json(path,saved)
    pending=repeated_scenes(story['scenes'])
    if pending:
        raise StoryValidationError('repeated_story_lines',dict(pending_scenes=pending,
            requests=saved['requests'],rejections=saved['rejections']))


def visual_batch(root,story,slots,identity):
    schema=object_schema({f'scene_{i}':string(30,360) for i in slots})
    response=ask(schema,
        'Storyboard the FINAL Hindi narration faithfully. For every requested scene return a compact English image prompt. '
        'Show exactly the concrete action, object and location described in that text. No generic unrelated scenery. '
        'Use the canonical age, hair, clothing colors, props and architecture consistently. State visible appearance explicitly, '
        'not just a character name. At most two visible people. Never invent a new character or change clothes. '
        'One action per frame, main person and prop clear, same colorful 3D storybook style. '
        'Keep each prompt under about 60 English words, put action and defining appearance first. '
        'Canonical cast: '+story['characters']+' World: '+story['world']+
        '\nCanonical plot: '+story['summary']+
        '\nFinal chronological beats for this batch: '+json.dumps(scene_context(story,slots),ensure_ascii=False)+
        '\nRequested indices: '+json.dumps(slots),
        int(identity[:7],16)+slots[0],min(3500,400+180*len(slots)),
        checkpoint=Path(root)/'visual-responses'/f'{slots[0]}.json')
    return {str(i):response[f'scene_{i}'] for i in slots}


def thumbnail_plan(root,story,identity):
    response=ask(object_schema({'scene':{'type':'integer','minimum':0,'maximum':len(story['scenes'])-1},
                                'thumbnail_prompt':string(80,360)}),
        'Choose the single scene that most truthfully represents this story main conflict or meaningful choice. '
        'Also write a SEPARATE English image-generation prompt designed for a YouTube thumbnail at small mobile size. '
        'This is a fresh composition, not a screenshot. Use the same canonical character appearance and actual '
        'event/prop/setting of the selected scene. One dominant expressive face, one clear story object, '
        'strong subject/background contrast, bright face lighting, bold saturated complementary colors, '
        'uncluttered composition, instantly readable emotional stakes, no tiny details, no text or lettering. '
        'Create curiosity about the real conflict without inventing danger, wealth, tears or plot events. '
        'Use polished 3D storybook graphics. A beautiful adult woman may be the focal character only when she is in the actual scene; preserve her canonical age and appearance. '
            'Show the moment before the real choice or reveal, leaving its outcome unseen to create a curiosity gap. '
            'Start with the large story object and its unresolved visual clue, then the character reacting beside it. '
        'Use a medium shot with face and object both clearly visible, not an isolated beauty portrait. '
        'Keep the core composition within 40 English words, with clothing and scenery last. '
        'No unrelated poster, invented event, or generic sunrise. Canonical cast: '+story['characters']+' World: '+story['world']+' '
        'Title: '+story['title']+' Summary: '+story['summary']+
        '\nFinal spoken beats: '+json.dumps(scene_context(story,range(len(story['scenes'])),neighbors=0),ensure_ascii=False),
        int(identity[:7],16),500,checkpoint=Path(root)/'thumbnail-selection.json')
    return dict(thumbnail_scene=response['scene'],thumbnail_prompt=response['thumbnail_prompt'])


def prepare_visuals(root, story):
    path=Path(root)/'visual-plan.json'
    identity=text_hash(json.dumps(story,sort_keys=True,ensure_ascii=False))
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved and saved.get('identity')!=identity:saved={}
    saved.setdefault('identity',identity);saved.setdefault('scenes',{})
    for start in range(0,len(story['scenes']),8):
        slots=list(range(start,min(start+8,len(story['scenes']))))
        if not all(str(i) in saved['scenes'] for i in slots):
            saved['scenes'].update(visual_batch(root,story,slots,identity))
            save_json(path,saved)
    if 'thumbnail_scene' not in saved or 'thumbnail_prompt' not in saved:
        saved.update(thumbnail_plan(root,story,identity));save_json(path,saved)
    story['visuals']=saved['scenes']
    story['thumbnail_scene']=saved['thumbnail_scene'];story['thumbnail_prompt']=saved['thumbnail_prompt']
