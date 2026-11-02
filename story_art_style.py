"""Compact shared art direction, placed before scene detail for CLIP encoders."""
VERSION = 'storybook-events-3d-v10'
CAST_DIRECTION = (
    'Give every character a fair complexion, attractive harmonious facial features and clear face lighting, '
    'while preserving their exact age, identity and distinct appearance. '
    'Adult women have strikingly beautiful refined features, expressive eyes, elegant hair, '
    'subtle makeup and tasteful flattering clothes consistent with their established outfit. '
    'Keep children age-appropriate and preserve elderly characters as elderly. '
)
STYLE = ('Realistic cinematic 3D storybook render, attractive characters, fair skin, lifelike facial proportions, '
         'natural skin texture, soft volumetric lighting. ')


def art_prompt(scene, kind='background'):
    if kind == 'reference':
        return 'Realistic cinematic 3D character reference. '+scene+' Natural proportions, fair skin, no text.'
    # Action/object must lead both CLIP encoders. Appearance cannot displace the story.
    return ('Realistic 3D narrative scene. '+scene+
            ' Realistic cinematic 3D storybook, expressive attractive characters, fair skin, soft light, no text.')


def focused_prompt(record, kind='background', attempt=0):
    """Put visible story nouns inside the short CLIP context, before cast detail."""
    import re
    text=record['event']
    nouns=('notebook','letter','toy','book','door','key','box','bag','photograph','phone','tree','house','school')
    answers=' '.join(a for check in record['checks'] for a in check['answers'])
    anchor=next((word for word in nouns if re.search(r'\b'+word+r's?\b',text,re.I)
                 and re.search(r'\b'+word+r's?\b',answers,re.I)),None)
    if anchor is None:return art_prompt(record['prompt'],kind)
    broken=bool(re.search(r'\b(?:broken|damaged)\s+(?:\w+\s+){0,2}'+anchor+r'\b|\b'+anchor+r'\s+(?:\w+\s+){0,2}(?:broke|broken|damaged)\b',text,re.I))
    foreground=('Broken ' if broken else '')+anchor+' in foreground, large and clearly visible. '
    # Quoted dialogue is narration, not text that should be drawn into the image.
    event=re.split(r'\s+and\s+(?:said|says)\b',text,flags=re.I)[0]
    event=re.sub(r'(?<!\w)\'[^\']*\'(?!\w)|"[^"]*"','',event)
    event=' '.join(event.split()[:18]).rstrip(' ,.;')
    parts=record['people'].split(';')
    people=[]
    for part in parts:
        part=re.sub(r',?\s*(?:short|curly|long|straight)?\s*(?:black|brown|grey|gray|white)?\s*hair\b.*','',part,flags=re.I)
        part=re.sub(r'\b(?:with|cotton|the|wearing)\b','',part,flags=re.I)
        people.append(' '.join(part.split()[:max(6,18//len(parts))]).strip(' ,'))
    setting=' '.join(record['setting'].split()[:5]).rstrip(' ,.;')
    framing='Wide composition. ' if attempt else ''
    return foreground+framing+event+'. '+'; '.join(people)+'. '+setting+'. Realistic cinematic 3D storybook, attractive faces, fair skin.'
