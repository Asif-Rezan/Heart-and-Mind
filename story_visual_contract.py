"""Tie every composition and visual check to an exact spoken story scene."""
import re

VERSION = 'story-events-v7'
ENGLISH_PATTERN = r'^[^\u0900-\u097f]*[A-Za-z][^\u0900-\u097f]*$'


def contract_schema():
    schema = {'type': 'object', 'additionalProperties': False,
            'required': ['prompt', 'event', 'people', 'setting', 'evidence', 'checks'], 'properties': {
        'prompt': {'type': 'string', 'minLength': 40, 'maxLength': 360},
        'event': {'type':'string','minLength':15,'maxLength':160},
        'people': {'type':'string','minLength':10,'maxLength':130},
        'setting': {'type':'string','minLength':5,'maxLength':60},
        'planning_review': {'type':'object'},
        'fallback': {'type':'object'},
        'evidence': {'type': 'string', 'minLength': 8, 'maxLength': 360},
        'checks': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['question', 'answers'], 'properties': {
                'question': {'type': 'string', 'minLength': 8, 'maxLength': 140},
                'answers': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                            'items': {'type': 'string', 'minLength': 1, 'maxLength': 40}}}}}}}

    for field in ('prompt','event','people','setting'):
        schema['properties'][field]['pattern']=ENGLISH_PATTERN
    check=schema['properties']['checks']['items']['properties']
    check['question']['pattern']=ENGLISH_PATTERN
    check['answers']['items']['pattern']=ENGLISH_PATTERN
    return schema


DIRECTION = (
    'Return a literal composition record: event, people, setting, evidence and checks. '
    'Event: concrete action and key story object FIRST, at most 160 characters; never start with camera, scenery or beauty. '
    'People: describe each actor with a generic visible role (man, woman, boy or girl), exact age and fixed clothes; at most 130 characters. '
    'Names alone do not tell an image model the actor gender/age. Include the visible role explicitly. '
    'Setting: canonical location, at most 60 characters. '
    'Evidence: an EXACT quote from this requested final Hindi scene that supports the visible event. '
    'Use ONLY the requested scene for props/actions; do not borrow facts from nearby scenes. '
    'Do not invent danger, magic, wealth, props or discoveries. Ordinary spatial staging is allowed. '
    'First write literal_scene as a plain English translation of ONLY the requested narration, without interpretation. '
    'Then depict that translation. Preserve stated actions; anger is an expression, never permission to slam or throw things. '
    'Use ONE open visual question checking the key story object; at most one additional interaction check. '
    'Ask about visible categories, not an earlier or later event. '
    'Use generic people labels (man, woman, girl), NEVER fictional names or invisible family relationships '
    'in questions/answers. Questions start What, Who, Where or How many; no yes/no questions, '
    'no expected-answer hints in the question, no beauty/skin/clothing checks. '
    'The checked action and object state must agree with the composition: an object cannot be held '
    'and on the ground at the same time. Answer alternatives are short visible category labels, '
    'not sentences or guesses about unseen details; omit articles and size/material adjectives. '
    'For counts use English number words. Every event/people/setting/question/answer field is English; '
    'ONLY evidence copies the Hindi source. '
)


def validate_contract(record, scene):
    from jsonschema import Draft202012Validator
    if not Draft202012Validator(contract_schema()).is_valid(record):
        raise ValueError('visual_contract_invalid')
    if record['prompt']!=compile_contract(record)['prompt']:
        raise ValueError('visual_composition_order_mismatch')
    if re.match(r'^(?:a |the )?(?:medium|wide|close|portrait|cinematic)\b',record['event'],flags=re.I):
        raise ValueError('visual_event_is_camera_description')
    if record['evidence'] not in scene['text']:
        raise ValueError('visual_evidence_not_in_scene')
    if re.search(r'[\u0900-\u097f]', record['prompt']):
        raise ValueError('visual_prompt_not_english')
    names = re.findall(r'\b([A-Z][a-z]+),?\s+\d{1,3}\b', record['people'])
    for check in record['checks']:
        checked = check['question'] + ' ' + ' '.join(check['answers'])
        if any(re.search(r'\b'+re.escape(name)+r'\b', checked, flags=re.I) for name in names):
            raise ValueError('visual_check_uses_fictional_name_use_visible_category')
        question = check['question'].strip().lower()
        if not re.match(r'^(what|who|where|how many)\b', question):
            raise ValueError('visual_question_not_open')
        if any(not re.search(r'[a-zA-Z0-9]', answer) or re.search(r'[\u0900-\u097f]',answer) or
               answer.strip().lower() in ('yes', 'no', 'unknown', 'nothing', 'none') for answer in check['answers']):
            raise ValueError('visual_answer_not_grounded')
    return record


def install_visuals(story, records):
    story['visuals'] = {key: value['prompt'] for key, value in records.items()}
    story['visual_contracts'] = records
    story['visual_plan_version'] = VERSION


def require_visuals(story):
    if story.get('visual_plan_version') != VERSION:
        raise ValueError('visual_plan_outdated_replan_from_prose')
    records = story.get('visual_contracts', {})
    if set(records) != {str(i) for i in range(len(story['scenes']))}:
        raise ValueError('visual_contract_coverage')
    for key, record in records.items():
        validate_contract(record, story['scenes'][int(key)])
        if not is_fallback(record) and (record.get('planning_review',{}).get('passed') is not True or record['planning_review'].get('version')!=REVIEW_VERSION):
            raise ValueError('visual_planning_review_missing')
        if record['prompt'] != story['visuals'][key]:
            raise ValueError('visual_prompt_contract_mismatch')
    selected = story['thumbnail_scene']
    record = validate_contract(story['thumbnail_contract'], story['scenes'][selected])
    if not is_fallback(record) and (record.get('planning_review',{}).get('passed') is not True or record['planning_review'].get('version')!=REVIEW_VERSION):
        raise ValueError('thumbnail_planning_review_missing')
    if record['prompt'] != story['thumbnail_prompt']:
        raise ValueError('thumbnail_prompt_contract_mismatch')
    if not isinstance(story.get('thumbnail_question'), str) or not story['thumbnail_question'].strip():
        raise ValueError('thumbnail_question_missing')


def composition_schema():
    """The model supplies facts; code puts the event before cast and scenery."""
    schema = contract_schema()
    schema['properties'].pop('prompt')
    schema['required'].remove('prompt')
    schema['properties'].pop('planning_review',None)
    schema['properties']={'literal_scene':{'type':'string','minLength':10,'maxLength':400,'pattern':ENGLISH_PATTERN},**schema['properties']}
    schema['required'].insert(0,'literal_scene')
    return schema


def compile_contract(record):
    result={key:record[key] for key in ('event','people','setting','evidence','checks')}
    result['prompt']='. '.join(result[key].rstrip(' .') for key in ('event','people','setting'))+'.'
    return result


REVIEW_VERSION = 'literal-scene-review-v3'
REVIEW_SCHEMA = {
    'type':'object','additionalProperties':False,
    'required':['source_translation','unsupported_details','faithful','visible_event','checks_observable','story_conflict','outcome_hidden','issues'],
    'properties':{'source_translation':{'type':'string','minLength':10,'maxLength':500,'pattern':ENGLISH_PATTERN},
        'unsupported_details':{'type':'array','maxItems':6,'items':{'type':'string','minLength':3,'maxLength':180,'pattern':ENGLISH_PATTERN}}, **{key:{'type':'boolean'} for key in (
        'faithful','visible_event','checks_observable','story_conflict','outcome_hidden')},
        'issues':{'type':'array','maxItems':4,'items':{'type':'string','minLength':5,'maxLength':220}}}}


def assess_plan(record,scene,cast,world,seed,checkpoint,viewer_question=None,ask_fn=None):
    if ask_fn is None:
        from story_writer import ask as ask_fn
    import json
    verdict=ask_fn(REVIEW_SCHEMA,
        'First translate ONLY FINAL NARRATION literally into source_translation, without adding actions. '
        'Next enumerate in unsupported_details EVERY candidate action/prop/state absent from that translation. '
        'Then independently audit the proposed image. Be strict: plausible additions still count as invented. '
        'For example anger does not imply throwing, picking up, burning, hitting or discarding an object. '
        'A broken object does not imply anyone broke it deliberately or is holding it. '
        'If narration is ambiguous, preserve that ambiguity; do not complete a missing story event. '
        'Allow ordinary static staging required to draw a frame: a mentioned object rests on a surface, '
        'a broken object shows damage, canonical architecture appears behind the scene, '
        'and stated anger becomes an angry facial expression. These are not new plot events. '
        'Do not require a reaction from every cast member. Reject new causal actions, additional props '
        'or unsupported specific object types (for example car when the source only says toy). '
        'Do not use events from neighboring scenes or assume missing props/actions. '
        'Canonical cast and world may supply appearance/location only. Ordinary camera staging is allowed, '
        'but inventing a notebook, making a person hold an unmentioned object, or contradictory object states is not. '
        'Set faithful=false for any unsupported important prop, event, action or reaction. '
        'Set visible_event=false if this is only a setting, abstract thought or beauty portrait. '
        'Set checks_observable=false if the checks fail to verify the key event/object, ask fictional proper names, invisible relationships, '
        'or require a prop/action absent from the composition. Answers must be generic visible labels '
        'like man, woman, girl, toy or notebook; an image reviewer cannot know fictional names. '
        'For a thumbnail require a clear concrete conflict/decision/discovery with a real unresolved '
        'viewer question and leave its outcome unseen; a quiet solo portrait is not a conflict. '
        'For backgrounds, story_conflict and outcome_hidden are informational only; never add issues for those two fields. '
        'Explain failures of applicable criteria briefly in English issues. When all applicable criteria pass use issues=[]. '
        'Any issue means the plan is rejected. Do not rewrite the script. '
        'FINAL NARRATION: '+scene['text']+'\nCAST: '+cast+'\nWORLD: '+world+
        '\nCANDIDATE: '+json.dumps(record,ensure_ascii=False)+
        '\nTHUMBNAIL VIEWER QUESTION: '+str(viewer_question or 'Not a thumbnail; judge fidelity and visibility.'),
        seed,700,checkpoint=checkpoint)
    passed=not verdict.get('unsupported_details') and all(verdict[key] for key in ('faithful','visible_event','checks_observable')) and not verdict['issues']
    if viewer_question is not None:passed=passed and verdict['story_conflict'] and verdict['outcome_hidden']
    return dict(version=REVIEW_VERSION,passed=bool(passed),verdict=verdict)


FALLBACK_EVENT = 'An atmospheric establishing view of the story setting without plot action'
FALLBACK_PEOPLE = 'No characters are shown in this establishing frame'


def is_fallback(record):
    if record.get('fallback',{}).get('mode') in ('literal-scene','scene-recovery','authored-scene'):
        return record.get('event') == record['fallback'].get('literal_event') and record.get('planning_review',{}).get('passed') is False
    return (record.get('fallback',{}).get('mode') == 'setting-only' and
            record.get('event') == FALLBACK_EVENT and record.get('people') == FALLBACK_PEOPLE)


def fallback_contract(scene, world, reason, cast=''):
    # The writer already paired this exact spoken beat with an English visual.
    # Keep that scene when a later planning request fails; never erase its actors.
    visual=' '.join(str(scene.get('visual','')).split())
    mixed=bool(re.search(r'[\u0900-\u097f]',visual))
    if mixed:
        visual=' '.join(re.sub(r'[^ -~]',' ',visual).split()).strip(' ,.;')
        # Preserve only recoverable English details; never invent a translated action.
        for noun,pattern in (('notebook',r'नोटबुक'),('letter',r'चिट्ठी|पत्र'),('toy',r'खिलौन'),('book',r'किताब|पुस्तक'),('drawing',r'चित्र')):
            if re.search(pattern,scene['text']) and not re.search(r'\b'+noun+r'\b',visual,re.I):visual+=', '+noun
    if 15<=len(visual) and re.fullmatch(ENGLISH_PATTERN,visual):
        # The writer often puts outfit clauses before the action. Move appearance
        # into people so token compaction cannot remove the actual narrated action.
        clauses=[part.strip() for part in visual.split(',') if part.strip()]
        appearance=r'\b(?:shirt|kurta|sari|vest|chunni|hair|borders|wearing|wears)\b'
        action=r'\b(?:standing|sitting|looking|holding|carrying|drawing|listening|smiling|opening|picks|reads|points)\b'
        kept=[part for i,part in enumerate(clauses) if i==0 or not (part.isdigit() or (re.search(appearance,part,re.I) and not re.search(action,part,re.I)))]
        event=', '.join(kept)
        if len(event)<15:event+=' in the established story scene'
        if len(event)>160:event=event[:161].rsplit(' ',1)[0]
        profiles=[]
        for profile in cast.split(';'):
            name=profile.strip().split(',')[0].strip().split(' ')[0] if profile.strip() else ''
            if name and re.search(r'\b'+re.escape(name)+r"\b(?!['’]s\b)",visual,re.I):
                profile=re.sub(r',?\s*(?:short|curly|long)?\s*(?:black|grey|gray|white)?\s*hair\b.*','',profile,flags=re.I)
                profile=re.sub(r',?\s*(?:always carries|walks with).*','',profile,flags=re.I)
                profiles.append(profile.strip())
        if profiles:
            cap=max(16,126//len(profiles))
            people='; '.join(p if len(p)<=cap else p[:cap+1].rsplit(' ',1)[0] for p in profiles)
        else:
            descriptors=[part for i,part in enumerate(clauses) if i==0 or (re.search(appearance,part,re.I) and not re.search(action,part,re.I))]
            people=', '.join(descriptors)
            if len(people)>130:people=people[:131].rsplit(' ',1)[0]
            if len(people)<10:people='The people described in this scene, with their established appearance'
        anchors=('notebook','letter','toy','book','door','key','box','bag','photograph','phone','drawing','tree','house','school')
        anchor=next((w for w in anchors if re.search(r'\b'+w+r's?\b',event,re.I)),None)
        checks=[dict(question='What object is being shown?',answers=['notebook','book'] if anchor=='notebook' else [anchor])] if anchor else [dict(
            question='Who is shown in this scene?',answers=['person','people','man','woman','child','girl','boy'])]
        setting=' '.join(str(world).split())
        if len(setting)>60:setting=setting[:61].rsplit(' ',1)[0]
        if len(setting)<5 or re.search(r'[\u0900-\u097f]',setting):setting='The established story location'
        record=compile_contract(dict(event=event,people=people,setting=setting,
            evidence=scene['text'][:300],checks=checks))
        record['fallback']=dict(mode='authored-scene',reason=reason,literal_event=event,partial_english=mixed)
        record['planning_review']=dict(version=REVIEW_VERSION,passed=False,
            issues=['Using this scene original writer visual; secondary planning was unavailable.'])
        return validate_contract(record,scene)
    # A neutral setting is the last resort only when no usable authored visual exists.
    setting = ' '.join(str(world).split())
    if len(setting)>60:setting=setting[:61].rsplit(' ',1)[0]
    setting=setting.rstrip(' ,.;')
    if len(setting)<5 or re.search(r'[\u0900-\u097f]',setting): setting='A quiet storybook setting'
    record=compile_contract(dict(event=FALLBACK_EVENT,people=FALLBACK_PEOPLE,
        setting=setting,evidence=scene['text'][:300],
        checks=[dict(question='What is shown in the scene?',answers=['landscape','building','room','village'])]))
    record['fallback']=dict(mode='setting-only',reason=reason)
    record['planning_review']=dict(version=REVIEW_VERSION,passed=False,issues=['Planning unavailable; neutral establishing frame.'])
    return validate_contract(record,scene)


def literal_recovery(scene, candidate, reason):
    """Reuse the translation, never the rejected composition's invented action."""
    evidence=candidate.get('evidence','')
    if not evidence or evidence not in scene['text']:return None
    literal=candidate.get('literal_scene','').strip()
    if len(literal)<15 or not re.fullmatch(ENGLISH_PATTERN,literal):return None
    nouns=('notebook','letter','toy','book','door','key','box','bag','photograph','phone','tree','house','school')
    anchor=next((word for word in nouns if re.search(r'\b'+word+r's?\b',literal,re.I)),None)
    if anchor is None:return None
    event=literal if len(literal)<=160 else literal[:161].rsplit(' ',1)[0]
    if not re.search(r'\b'+anchor+r's?\b',event,re.I):return None
    record=compile_contract(dict(event=event,people=candidate['people'],setting=candidate['setting'],
        evidence=scene['text'][:300],checks=[dict(question='What object or place is central to the scene?',answers=[anchor])]))
    record['fallback']=dict(mode='literal-scene',reason=reason,literal_event=event)
    record['planning_review']=dict(version=REVIEW_VERSION,passed=False,
        issues=['Rejected composition replaced by literal translation; not independently approved.'])
    try:return validate_contract(record,scene)
    except ValueError:return None


def thumbnail_recovery(story, reason):
    """Choose an actual early authored interaction, never a generic landscape."""
    names=[p.strip().split(',')[0].split(' ')[0] for p in story['characters'].split(';') if p.strip()]
    objects=('notebook','letter','toy','book','key','box','bag','photograph','phone','drawing')
    def score(scene):
        visual=scene.get('visual','')
        actors=sum(bool(re.search(r'\b'+re.escape(name)+r"\b(?!['’]s\b)",visual,re.I)) for name in names)
        anchor=any(re.search(r'\b'+word+r's?\b',visual,re.I) for word in objects)
        return (anchor and actors>=2,anchor,actors,-scene['index'])
    scene=max(story['scenes'][:8],key=score)
    record=fallback_contract(scene,story['world'],reason,story['characters'])
    anchor=next((w for w in objects if re.search(r'\b'+w+r's?\b',record['event'],re.I)),None)
    question='What happens next with this '+anchor+'?' if anchor else 'What happens next in this story?'
    return dict(thumbnail_scene=scene['index'],thumbnail_prompt=record['prompt'],thumbnail_contract=record,thumbnail_question=question)
