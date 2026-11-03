"""Compact shared art direction, placed before scene detail for CLIP encoders."""
VERSION = 'storybook-events-3d-v11'
CAST_DIRECTION = (
    'Give every character a fair complexion, attractive harmonious facial features and clear face lighting, '
    'while preserving their exact age, identity and distinct appearance. '
    'Adult women have strikingly beautiful refined features, expressive eyes, elegant hair, '
    'subtle makeup and tasteful flattering clothes consistent with their established outfit. '
    'Keep children age-appropriate and preserve elderly characters as elderly. '
)
STYLE = ('Realistic cinematic 3D storybook render, attractive characters, fair skin, lifelike facial proportions, '
         'natural skin texture, soft volumetric lighting. ')


RENDER_STYLE = 'Cinematic 3D storybook render, polished CGI, realistic beautiful faces, fair skin, soft light. '

def art_prompt(scene, kind='background'):
    if kind == 'reference':
        return 'Realistic cinematic 3D character reference. '+scene+' Natural proportions, fair skin, no text.'
    # Action/object must lead both CLIP encoders. Appearance cannot displace the story.
    return RENDER_STYLE+scene+' No text.'


def focused_prompt(record, kind='background', attempt=0, token_count=None, max_tokens=77):
    """Put visible story nouns inside the short CLIP context, before cast detail."""
    import re
    if record.get('music_portrait'):
        return music_portrait_prompt(record,kind,token_count,max_tokens)
    text=record['event']
    nouns=('notebook','letter','toy','book','door','key','box','bag','photograph','phone','drawing','tree','house','school')
    answers=' '.join(a for check in record['checks'] for a in check['answers'])
    anchor=next((word for word in nouns if re.search(r'\b'+word+r's?\b',text,re.I)
                 and re.search(r'\b'+word+r's?\b',answers,re.I)),None)
    broken=anchor is not None and bool(re.search(r'\b(?:broken|damaged)\s+(?:\w+\s+){0,2}'+anchor+r'\b|\b'+anchor+r'\s+(?:\w+\s+){0,2}(?:broke|broken|damaged)\b',text,re.I))
    foreground=(('Broken ' if broken else '')+anchor+' in foreground, large and clearly visible. ') if anchor else ''
    # Quoted dialogue is narration, not text that should be drawn into the image.
    event=re.split(r'\s+and\s+(?:said|says)\b',text,flags=re.I)[0]
    event=re.sub(r'(?<!\w)\'[^\']*\'(?!\w)|"[^"]*"','',event)
    parts=record['people'].split(';')
    cleaned=[]
    for part in parts:
        part=re.sub(r',?\s*(?:short|curly|long|straight)?\s*(?:black|brown|grey|gray|white)?\s*hair\b.*','',part,flags=re.I)
        part=re.sub(r'\b(?:with|cotton|the|wearing|wears|a|an|and)\b','',part,flags=re.I)
        cleaned.append(' '.join(part.split()).strip(' ,'))
    framing='Wide shot. ' if attempt else ''
    # Actual tokenizer, including the safety suffix, determines the final budget.
    # Trim location/detail first; keep the visual style and each actor's leading age.
    budgets=((14,16,4),(10,12,2),(8,10,0),(6,10,0),(6,6,0),(4,6,0))
    for event_words,people_words,setting_words in budgets:
        action=' '.join(event.split()[:event_words]).rstrip(' ,.;')
        people='; '.join(' '.join(p.split()[:max(2,people_words//len(cleaned))]) for p in cleaned)
        setting=' '.join(record['setting'].split()[:setting_words]).rstrip(' ,.;')
        prompt=foreground+RENDER_STYLE+framing+action+'. '+people+'.'+(' '+setting+'.' if setting else '')
        if token_count is None or token_count(prompt)<=max_tokens:return prompt
    # Very long fictional names are identity metadata, not useful CLIP vocabulary.
    people=[]
    for part in cleaned:
        age=re.search(r'\b(\d{1,3})\b',part)
        role=next((r for r in ('woman','girl','boy','man','child') if re.search(r'\b'+r+r'\b',part,re.I)),'person')
        people.append(role+(' '+age[1] if age else ''))
    prompt=foreground+RENDER_STYLE+' '.join(event.split()[:4])+'. '+'; '.join(people)+'.'
    if token_count(prompt)>max_tokens:raise ValueError('story_prompt_encoder_budget')
    return prompt


def music_portrait_prompt(record, kind, token_count=None, max_tokens=77):
    """A single pair and neutral color survive the encoders' limited context."""
    import re
    couple = record['music_portrait']['couple']
    subject = ('A man in a T-shirt embracing a woman in a casual top, western clothing. '
               if couple else 'Adult woman in a casual top, western clothing, hopeful smile. ')
    framing = 'Chest-up, faces large. ' if kind == 'thumbnail' else 'Waist-up. '
    pose = 'Both faces visible, gentle smiles. ' if couple else 'Face visible. '
    lead = subject + framing + pose + 'Neutral white balance, natural skin tones, daylight, sharp eyes. '
    # Repeating the event's actors made the small model invent a third person.
    # Use only environmental anchors after the pair; never copy warm-light cues.
    anchors = [word for word in ('rain', 'window', 'door', 'courtyard', 'bookshop', 'river', 'platform')
               if re.search(r'\b'+word+r'\b', record['event'], re.I)]
    scene = ', '.join(anchors[:2])
    for detail in (scene, ''):
        prompt = lead + (detail + '. ' if detail else '') + 'Natural colors, cinematic photograph, no text.'
        if token_count is None or token_count(prompt) <= max_tokens:
            return prompt
    raise ValueError('music_prompt_encoder_budget')
