"""Lightweight fixtures for image orchestration tests; no model inference."""
from story_visual_contract import install_visuals
from story_image_review import VERSION, MODEL, REVISION, digest


def record_for(scene, prompt=None):
    return dict(prompt=prompt or scene['visual'], evidence=scene['text'][:300],
                checks=[dict(question='What is the person holding?',answers=['letter','book'])])


def attach_contracts(story):
    install_visuals(story,{str(s['index']):record_for(s,story.get('visuals',{}).get(str(s['index']),s['visual'])) for s in story['scenes']})
    story.setdefault('thumbnail_scene',0)
    record=record_for(story['scenes'][story['thumbnail_scene']],story.get('thumbnail_prompt'))
    story.update(thumbnail_prompt=record['prompt'],thumbnail_contract=record,
                 thumbnail_question='What choice will the shopkeeper make about the letter?')
    return story


def passed_review(path, checks):
    return dict(version=VERSION,model=MODEL,revision=REVISION,checked_sha256=digest(path),
                passed=True,answers=[dict(question=c['question'],answer=c['answers'][0],passed=True) for c in checks])
