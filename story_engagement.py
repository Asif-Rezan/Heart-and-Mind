"""Script-specific hook, causal story progression, payoff and gentle closing CTA."""
import hashlib
import json
from pathlib import Path
from story_writer import ask, object_schema, string, save_json, speech_issues


def chapter_direction(index):
    directions=(
        'Open scene 0 with an immediate concrete dilemma, unexpected action or unanswered question. '
        'Hook within the first two short scenes (about 10 seconds); no greeting, channel intro or lesson spoiler. '
        'Quickly establish whose desire is at stake and why it matters.',
        'Escalate the obstacle through visible choices and consequences. Give a new clue or emotional shift '
        'every two or three scenes; do not repeat chapter 1 exposition.',
        'Make the setback cost something believable. Keep the outcome uncertain; no artificial disaster '
        'or narrator sermon. End on an unresolved choice that leads into the turning point.',
        'Reveal a credible discovery or changed perspective through action. Pay off an earlier detail '
        'and make the next decision feel earned, without revealing the whole ending.',
        'Show the protagonist act on that decision, meet resistance, and change the situation. '
        'Use specific sensory details and reactions, not a list of motivational advice.',
        'Resolve the central question and deliver the emotional payoff through a concrete consequence. '
        'Only AFTER the resolution, use the last one or two scenes for a brief natural narrator CTA: '
        'one specific reflective question about this story inviting a comment, then an optional short invitation '
        'to follow Heart and Mind for another story. No guilt, pressure, reward promise or repeated requests. '
        'The closing visual stays in the resolved story world; no invented on-screen text.'
    )
    return directions[index]


CRITERIA=('hook','progression','payoff','cta')
EDITOR_VERSION='fixed-editor-plan-v2'


def has_closing_cta(scenes):
    text=' '.join(s['text'] for s in scenes[-2:])
    return 'आप' in text and any(word in text for word in ('कमेंट','टिप्पणी','बताइ','लिखिए','बताएं','बताएँ'))


def editorial_tasks(review, scenes):
    from story_writer import StoryValidationError
    tasks={row['scene']:row['instruction'] for row in review['repairs']}
    if not review['progression'] and not tasks:
        raise StoryValidationError('editorial_plan_incomplete',dict(criteria=['progression']))
    if not review['hook']:
        tasks.setdefault(0,chapter_direction(0))
    if not review['payoff']:
        tasks.setdefault(max(0,len(scenes)-3),'Show the earned emotional consequence resolving the original dilemma. Preserve canonical events and names; no sermon.')
    if not review['cta'] or not has_closing_cta(scenes):
        tasks[len(scenes)-1]='After the resolved story, ask ONE specific reflective question inviting viewers to comment (आप / टिप्पणी / बताइए). Keep it brief; no pressure or reward. Visual stays in the story world.'
    return tasks


def polish_engagement(root,story):
    """Freeze one editorial plan; checkpoint validated edits without moving goals."""
    from story_writer import StoryValidationError, repeated_scenes, normalized
    from story_format import word_bounds
    from story_constraints import edit_word_limits, constrain_edits, hindi_cta_pattern
    minimum,maximum=word_bounds(story)
    last=len(story['scenes'])-1
    from story_plan import scene_context
    root=Path(root)
    identity=hashlib.sha256(json.dumps(story['scenes'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path=root/'engagement-review.json'
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved and saved.get('identity')!=identity:
        # Restored artifacts may contain an older upstream prose revision.
        # Never apply those edits to a different script; audit the current one.
        save_json(root/f"engagement-review-stale-{str(saved.get('identity','unknown'))[:12]}.json",saved)
        print(json.dumps(dict(phase='stale editorial checkpoint invalidated',identity=identity)),flush=True)
        saved={}
    if saved:
        story['scenes']=saved['scenes']
        story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
    if saved.get('version')!=EDITOR_VERSION:
        # Reuse the actual failed production audit and repaired prose; no hour-long restart.
        review=saved.get('review')
        if not review:
            schema=object_schema({**{key:{'type':'boolean'} for key in CRITERIA},
                'repairs':{'type':'array','maxItems':6,'items':object_schema({
                    'scene':{'type':'integer','minimum':0,'maximum':last},'instruction':string(10,240)})}})
            review=ask(schema,
                'Make ONE actionable editorial plan for this Hindi story. Assess hook in the first two scenes, '
                'causal progression, earned payoff and a brief reflective comment CTA only after the ending. '
                'For every real problem give its exact scene index and a concrete correction based on the '
                'canonical outline. Do not invent new characters, change relationships or impose new plot goals. '
                'Keep instructions concise. Do not mark a criterion false for stylistic preference alone. '
                'Canonical summary: '+story['summary']+' Cast: '+story['characters']+
                '\nFinal script: '+json.dumps(scene_context(story,range(len(story['scenes'])),neighbors=0),ensure_ascii=False),
                int(identity[:7],16),1300,checkpoint=root/'engagement-audit-0.json')
        tasks=editorial_tasks(review,story['scenes'])
        saved=dict(version=EDITOR_VERSION,identity=identity,scenes=story['scenes'],review=review,
                   tasks={str(i):value for i,value in tasks.items()},complete=[],approved=False,requests=0)
        save_json(path,saved)
    saved.setdefault('rejections',{})
    pending=[int(i) for i in saved['tasks'] if i not in saved['complete']]
    print(json.dumps(dict(phase='fixed editorial plan',pending_scenes=pending,completed_scenes=len(saved['complete']))),flush=True)
    for start in range(0,len(pending),2):
        slots=pending[start:start+2]
        for attempt in range(2):
            remaining=[i for i in slots if str(i) not in saved['complete']]
            if not remaining:break
            saved['requests']+=1
            save_json(path,saved)
            limits=edit_word_limits(story,remaining)
            schema=constrain_edits(object_schema({f'scene_{i}':object_schema({'text':string(20,400),'visual':string(20,360)}) for i in remaining}),limits)
            if last in remaining:
                schema['properties'][f'scene_{last}']['properties']['text']['pattern'] = hindi_cta_pattern(
                    limits[last]['minimum_words'], limits[last]['maximum_words'])
            response=ask(schema,
                f'Execute ONLY the frozen editorial corrections below. The complete story has {len(story["lyrics"].split())} words and must stay within {minimum}-{maximum}. '
                'Replace the existing beat, never append extra exposition. Use the SAME number of Hindi words or fewer '
                'when close to the total maximum. Follow the exact per-scene word caps below; do not expand beyond them. '
                'one narrator; no repeated line, no new character, no changed relationship or canonical event. '
                'Preserve accepted scenes; do not reopen the review or invent additional requirements. '
                f'Update each English visual to represent the edited text. For scene {last} the spoken text MUST '
                'start with आप, ask a story-specific question, and end exactly with ? टिप्पणी में बताइए। '
                'The fixed opening and closing count toward the per-scene word cap. '
                'Canonical summary: '+story['summary']+' Cast: '+story['characters']+
                '\nFinal neighboring beats: '+json.dumps(scene_context(story,remaining),ensure_ascii=False)+
                '\nRequested current visuals: '+json.dumps({i:story['scenes'][i]['visual'] for i in remaining},ensure_ascii=False)+
                '\nFrozen corrections: '+json.dumps({i:saved['tasks'][str(i)] for i in remaining},ensure_ascii=False)+
                '\nRejected candidates to condense or correct: '+json.dumps({str(i):saved.get('rejected_candidates',{}).get(str(i)) for i in remaining},ensure_ascii=False)+
                '\nPer-scene word limits: '+json.dumps(limits)+
                '\nPrevious rejection feedback: '+json.dumps({str(i):saved['rejections'].get(str(i)) for i in remaining}),
                (int(identity[:7],16)+saved['requests']+100)%(2**31-3),1600,
                checkpoint=root/f"engagement-edit-{saved['requests']}.json")
            for i in remaining:
                value=response[f'scene_{i}']
                reason=None
                if normalized(value['text'])==normalized(story['scenes'][i]['text']):reason='unchanged_text'
                elif speech_issues(value['text']):reason='invalid_hindi'
                elif i==last and not has_closing_cta([value]):reason='closing_cta_missing'
                proposed=[dict(s) for s in story['scenes']]
                proposed[i]=dict(value,index=i,speaker='narrator')
                total=sum(len(s['text'].split()) for s in proposed)
                if not reason and not minimum<=total<=maximum:reason='story_word_budget'
                if not reason and not set(repeated_scenes(proposed)).issubset(set(repeated_scenes(story['scenes']))):reason='new_repeated_line'
                if reason:
                    saved['rejections'][str(i)]=dict(reason=reason,proposed_total_words=total,
                        minimum_words=minimum,maximum_words=maximum,
                        maximum_scene_words=limits[i]['maximum_words'])
                    saved.setdefault('rejected_candidates',{})[str(i)]=value
                    save_json(path,saved)
                    print(json.dumps(dict(phase='editorial edit rejected',scene=i,**saved['rejections'][str(i)])),flush=True)
                    continue
                saved['rejections'].pop(str(i),None)
                saved.get('rejected_candidates',{}).pop(str(i),None)
                story['scenes']=proposed
                story['lyrics']='\n'.join(s['text'] for s in proposed)
                saved['scenes']=proposed
                saved['complete'].append(str(i))
                save_json(path,saved)
                print(json.dumps(dict(phase='editorial edit saved',scene=i,pending=len(saved['tasks'])-len(saved['complete']))),flush=True)
        missing=[i for i in slots if str(i) not in saved['complete']]
        if missing:
            raise StoryValidationError('editorial_edit_incomplete',dict(pending_scenes=missing,requests=saved['requests'],
                rejections={str(i):saved['rejections'].get(str(i)) for i in missing}))
    if not has_closing_cta(story['scenes']):
        raise StoryValidationError('story_closing_cta_missing')
    # Completion means the fixed edits passed content checks, not a claimed audience rating.
    saved['approved']=True
    saved['approval_basis']='fixed_plan_edits_validated'
    save_json(path,saved)
