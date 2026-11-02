"""Tie every composition and visual check to an exact spoken story scene."""
import re

VERSION = 'story-events-v1'


def contract_schema():
    return {'type': 'object', 'additionalProperties': False,
            'required': ['prompt', 'evidence', 'checks'], 'properties': {
        'prompt': {'type': 'string', 'minLength': 40, 'maxLength': 360},
        'evidence': {'type': 'string', 'minLength': 8, 'maxLength': 360},
        'checks': {'type': 'array', 'minItems': 1, 'maxItems': 3, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['question', 'answers'], 'properties': {
                'question': {'type': 'string', 'minLength': 8, 'maxLength': 140},
                'answers': {'type': 'array', 'minItems': 1, 'maxItems': 8,
                            'items': {'type': 'string', 'minLength': 1, 'maxLength': 40}}}}}}}


DIRECTION = (
    'Return a grounded visual record with prompt, evidence and checks. '
    'Evidence must be an EXACT quote from the selected FINAL Hindi spoken scene, not its old visual description. '
    'The English prompt starts with the concrete event and important story object or interaction, then '
    'the canonical people, clothes and setting. Use a medium-wide narrative composition, not a posed portrait. '
    'Do not invent any prop, person, danger, magic, wealth or reveal absent from the narration. '
    'Keep the core event within 35 English words so it survives the image encoder. '
    'Supply 1-3 short OPEN visual questions and acceptable short English answers to verify the '
    'key story object/action or interaction in the actual pixels. Questions start with What, Who, '
    'Where or How many; do not mention the expected answer in the question or use yes/no questions. '
    'For example: What is the girl holding? answers: notebook, book. '
    'Checks must verify the event, not beauty, skin tone or wardrobe. '
)


def validate_contract(record, scene):
    from jsonschema import Draft202012Validator
    if not Draft202012Validator(contract_schema()).is_valid(record):
        raise ValueError('visual_contract_invalid')
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
        if record['prompt'] != story['visuals'][key]:
            raise ValueError('visual_prompt_contract_mismatch')
    selected = story['thumbnail_scene']
    record = validate_contract(story['thumbnail_contract'], story['scenes'][selected])
    if record['prompt'] != story['thumbnail_prompt']:
        raise ValueError('thumbnail_prompt_contract_mismatch')
    if not isinstance(story.get('thumbnail_question'), str) or not story['thumbnail_question'].strip():
        raise ValueError('thumbnail_question_missing')
