"""CPU visual checks: reject missing story anchors instead of publishing portraits."""
import hashlib
import json
import os
from pathlib import Path
import re

MODEL = 'Salesforce/blip-vqa-base'
REVISION = '787b3d35d57e49572baabd22884b3d5a05acf072'
VERSION = 'open-vqa-v4'
_processor = _model = None


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(text):
    counts=dict(one='1',two='2',three='3',four='4',five='5',six='6',seven='7',eight='8',nine='9',ten='10')
    return ' '.join(counts.get(word,word) for word in re.findall(r'[a-z0-9]+', text.lower()))


def matches(answer, expected):
    answer = normalized(answer)
    if not answer or re.search(r'\b(no|none|nothing|without|not|unknown|cannot)\b', answer):
        return False
    acceptable = [normalized(item) for item in expected if normalized(item)]
    return any(re.search(r'\b'+re.escape(item)+r's?\b', answer) for item in acceptable)


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
            review.get('revision') == REVISION and (review.get('passed') is True or review.get('fallback') in ('best-candidate','neutral-background')) and
            review.get('source_sha256') == digest(target))


def generate_reviewed(prompt, path, seed, contract, kind='background', **kwargs):
    from story_image_cpu import generate
    from story_thumbnail import export_thumbnail
    from story_writer import save_json
    path = Path(path)
    work = path.parent/'image-review'/path.stem
    work.mkdir(parents=True, exist_ok=True)
    reports = []
    for attempt in range(2):
        candidate = work/f'candidate-{attempt}.png'
        from story_art_style import focused_prompt
        composition = focused_prompt(contract,kind,attempt)
        try:
            used_prompt=generate(composition, candidate, seed=seed+attempt*7919,
                     negative_extra='headshot, beauty portrait, fashion editorial, isolated face, '+contract.get('negative_extra',''),
                     story_contract=contract,kind=kind,composition_attempt=attempt,**kwargs)
            if isinstance(used_prompt,str):composition=used_prompt
            from PIL import Image
            with Image.open(candidate) as image:image.verify()
            checked = candidate
            if kind == 'thumbnail':
                checked = candidate.with_suffix('.jpg')
                export_thumbnail(candidate, checked)
            try:
                report = review_image(checked, contract['checks'])
            except Exception as exc:
                report = dict(version=VERSION,model=MODEL,revision=REVISION,passed=False,
                              answers=[],error_type=type(exc).__name__)
            report.update(attempt=attempt, prompt=composition, source_sha256=digest(candidate))
        except Exception as exc:
            report = dict(version=VERSION,model=MODEL,revision=REVISION,passed=False,
                          answers=[],attempt=attempt,error_type=type(exc).__name__)
        report['planning_fallback']=contract.get('fallback',{}).get('mode')
        report['story_verified']=bool(report['passed'] and contract.get('planning_review',{}).get('passed') and not report['planning_fallback'])
        reports.append(report)
        save_json(work/'reviews.json', reports)
        print(json.dumps(dict(phase='story image review',kind=kind,attempt=attempt,passed=report['passed'],answers=report['answers'])),flush=True)
        if report.get('error_type') == 'ImageSafetyBlocked':break
        if report['passed']:
            path.parent.mkdir(parents=True,exist_ok=True)
            candidate.replace(path)
            return report
    # A failed quality/service check must not discard narration or stop the video.
    available=[r for r in reports if r.get('source_sha256')]
    if available:
        report=max(available,key=lambda r:sum(a.get('passed',False) for a in r['answers'])).copy()
        (work/f"candidate-{report['attempt']}.png").replace(path)
        report['fallback']='best-candidate'
    else:
        neutral_background(path,kwargs.get('width',1024),kwargs.get('height',576),seed)
        report=dict(version=VERSION,model=MODEL,revision=REVISION,passed=False,answers=[],
                    fallback='neutral-background',error_type='generation_unavailable')
    report['source_sha256']=digest(path)
    report['planning_fallback']=contract.get('fallback',{}).get('mode')
    report['story_verified']=False
    save_json(work/'fallback.json',report)
    print(json.dumps(dict(phase='story image fallback',kind=kind,mode=report['fallback'])),flush=True)
    return report


def neutral_background(path,width,height,seed):
    """Offline, text-free emergency asset; never pretends to depict a plot event."""
    from PIL import Image, ImageDraw, ImageFilter
    image=Image.new('RGB',(width,height))
    draw=ImageDraw.Draw(image)
    for y in range(height):
        ratio=y/max(1,height-1)
        draw.line((0,y,width,y),fill=(int(25+50*ratio),int(37+38*ratio),int(62+20*ratio)))
    draw.ellipse((width*.55,-height*.3,width*1.3,height*.8),fill=(127,96,70))
    image=image.filter(ImageFilter.GaussianBlur(max(1,width/18)))
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    image.save(path)
