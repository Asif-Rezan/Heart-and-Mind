"""Tie every composition and visual check to an exact spoken story scene."""
import re

VERSION = 'story-events-v2'


def contract_schema():
    return {'type': 'object', 'additionalProperties': False,
            'required': ['prompt', 'event', 'people', 'setting', 'evidence', 'checks'], 'properties': {
        'prompt': {'type': 'string', 'minLength': 40, 'maxLength': 360},
        'event': {'type':'string','minLength':15,'maxLength':160},
        'people': {'type':'string','minLength':10,'maxLength':130},
        'setting': {'type':'string','minLength':5,'maxLength':60},
        'planning_review': {'type':'object'},
        'evidence': {'type': 'string', 'minLength': 8, 'maxLength': 360},
        'checks': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['question', 'answers'], 'properties': {
                'question': {'type': 'string', 'minLength': 8, 'maxLength': 140},
                'answers': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                            'items': {'type': 'string', 'minLength': 1, 'maxLength': 40}}}}}}}


DIRECTION = (
    'Return a literal composition record: event, people, setting, evidence and checks. '
    'Event: concrete action and key story object FIRST, at most 160 characters; never start with camera, scenery or beauty. '
    'People: canonical actors, exact ages and fixed clothes, at most 130 characters. '
    'Setting: canonical location, at most 60 characters. '
    'Evidence: an EXACT quote from this requested final Hindi scene that supports the visible event. '
    'Use ONLY the requested scene for props/actions; do not borrow facts from nearby scenes. '
    'Do not invent danger, magic, wealth, props or discoveries. Ordinary spatial staging is allowed. '
    'Supply 1-3 OPEN visual questions about the key object/action/interaction and short English answer alternatives. '
    'Use generic people labels (man, woman, girl), NEVER fictional names or invisible family relationships '
    'in questions/answers. Questions start What, Who, Where or How many; no yes/no questions, '
    'no expected-answer hints in the question, no beauty/skin/clothing checks. '
    'The checked action and object state must agree with the composition: an object cannot be held '
    'and on the ground at the same time. Example: What is the girl holding? answers: notebook, book. '
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
    for check in record['checks']:
        question = check['question'].strip().lower()
        if not re.match(r'^(what|who|where|how many)\b', question):
            raise ValueError('visual_question_not_open')
        if any(not re.search(r'[a-zA-Z0-9]', answer) or re.search(r'[\u0900-\u097f]',answer) or
               answer.strip().lower() in ('yes', 'no', 'unknown', 'nothing') for answer in check['answers']):
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
        if record.get('planning_review',{}).get('passed') is not True or record['planning_review'].get('version')!=REVIEW_VERSION:
            raise ValueError('visual_planning_review_missing')
        if record['prompt'] != story['visuals'][key]:
            raise ValueError('visual_prompt_contract_mismatch')
    selected = story['thumbnail_scene']
    record = validate_contract(story['thumbnail_contract'], story['scenes'][selected])
    if record.get('planning_review',{}).get('passed') is not True or record['planning_review'].get('version')!=REVIEW_VERSION:
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
    return schema


def compile_contract(record):
    result={key:record[key] for key in ('event','people','setting','evidence','checks')}
    result['prompt']='. '.join(result[key].rstrip(' .') for key in ('event','people','setting'))+'.'
    return result


REVIEW_VERSION = 'literal-scene-review-v1'
REVIEW_SCHEMA = {
    'type':'object','additionalProperties':False,
    'required':['faithful','visible_event','checks_observable','story_conflict','outcome_hidden','issues'],
    'properties':{**{key:{'type':'boolean'} for key in (
        'faithful','visible_event','checks_observable','story_conflict','outcome_hidden')},
        'issues':{'type':'array','maxItems':4,'items':{'type':'string','minLength':5,'maxLength':220}}}}


def assess_plan(record,scene,cast,world,seed,checkpoint,viewer_question=None,ask_fn=None):
    if ask_fn is None:
        from story_writer import ask as ask_fn
    import json
    verdict=ask_fn(REVIEW_SCHEMA,
        'Independently audit this proposed image against ONE final narrated scene. Be strict. '
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
        'Explain every failed criterion briefly in English issues. Do not rewrite the script. '
        'FINAL NARRATION: '+scene['text']+'\nCAST: '+cast+'\nWORLD: '+world+
        '\nCANDIDATE: '+json.dumps(record,ensure_ascii=False)+
        '\nTHUMBNAIL VIEWER QUESTION: '+str(viewer_question or 'Not a thumbnail; judge fidelity and visibility.'),
        seed,700,checkpoint=checkpoint)
    passed=all(verdict[key] for key in ('faithful','visible_event','checks_observable'))
    if viewer_question is not None:passed=passed and verdict['story_conflict'] and verdict['outcome_hidden']
    return dict(version=REVIEW_VERSION,passed=bool(passed),verdict=verdict)
