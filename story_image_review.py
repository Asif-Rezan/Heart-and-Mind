"""CPU visual checks: reject missing story anchors instead of publishing portraits."""
import hashlib
import json
import os
from pathlib import Path
import re

MODEL = 'Salesforce/blip-vqa-base'
REVISION = '787b3d35d57e49572baabd22884b3d5a05acf072'
VERSION = 'open-vqa-v1'
_processor = _model = None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    return ' '.join(re.findall(r'[a-z0-9]+', text.lower()))


def matches(answer, expected):
    answer = normalized(answer)
    if not answer or re.match(r'^(no|none|nothing|unknown|cannot|can not)\b', answer):
        return False
    return any(re.search(r'\b'+re.escape(normalized(item))+r'\b', answer) for item in expected)


def review_image(path, checks):
    global _processor, _model
    import torch
    from PIL import Image
    from transformers import BlipProcessor, BlipForQuestionAnswering
    torch.set_num_threads(min(os.cpu_count() or 2, 4))
    if _model is None:
        _processor = BlipProcessor.from_pretrained(MODEL, revision=REVISION, token=False, use_fast=False)
        _model = BlipForQuestionAnswering.from_pretrained(
            MODEL, revision=REVISION, token=False, use_safetensors=True,
            low_cpu_mem_usage=True, trust_remote_code=False).to('cpu').eval()
    answers = []
    with Image.open(path) as source:
        image = source.convert('RGB')
        for check in checks:
            inputs = _processor(image, check['question'], return_tensors='pt')
            with torch.inference_mode():
                result = _model.generate(**inputs, max_new_tokens=12)
            answer = _processor.decode(result[0], skip_special_tokens=True)
            answers.append(dict(question=check['question'], answer=answer,
                                expected=check['answers'], passed=matches(answer, check['answers'])))
    return dict(version=VERSION, model=MODEL, revision=REVISION,
                checked_sha256=digest(path), passed=bool(answers) and all(a['passed'] for a in answers), answers=answers)


def cache_current(saved, plan, target):
    if not isinstance(saved, dict) or not Path(target).is_file():return False
    review = saved.get('review', {})
    return ({k:v for k,v in saved.items() if k != 'review'} == plan and
            review.get('version') == VERSION and review.get('model') == MODEL and
            review.get('revision') == REVISION and review.get('passed') is True and
            review.get('source_sha256') == digest(target))


def generate_reviewed(prompt, path, seed, contract, kind='background', **kwargs):
    from story_image_cpu import generate
    from story_thumbnail import export_thumbnail
    from story_writer import save_json, StoryValidationError
    path = Path(path)
    work = path.parent/'image-review'/path.stem
    work.mkdir(parents=True, exist_ok=True)
    reports = []
    for attempt in range(2):
        candidate = work/f'candidate-{attempt}.png'
        composition = prompt if attempt == 0 else (
            'Wide narrative scene. '+contract['prompt']+
            ' Show the complete action and the important story object prominently. Cinematic 3D render.')
        generate(composition, candidate, seed=seed+attempt*7919,
                 negative_extra='headshot, beauty portrait, fashion editorial, isolated face', **kwargs)
        checked = candidate
        if kind == 'thumbnail':
            checked = candidate.with_suffix('.jpg')
            export_thumbnail(candidate, checked)
        report = review_image(checked, contract['checks'])
        report.update(attempt=attempt, prompt=composition, source_sha256=digest(candidate))
        reports.append(report)
        save_json(work/'reviews.json', reports)
        print(json.dumps(dict(phase='story image review',kind=kind,attempt=attempt,passed=report['passed'],answers=report['answers'])),flush=True)
        if report['passed']:
            path.parent.mkdir(parents=True,exist_ok=True)
            candidate.replace(path)
            return report
    raise StoryValidationError('image_story_mismatch',dict(kind=kind,attempts=2,reviews=str(work/'reviews.json')))
