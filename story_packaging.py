"""Story-specific Hindi search packaging, checkpointed apart from spoken prose."""
import hashlib
import json
from pathlib import Path
from story_writer import ask, object_schema, string, save_json

VERSION='hindi-story-seo-v1'
DISCLOSURE='यह एक मौलिक काल्पनिक कहानी है। आवाज़, चित्र और संगीत AI की सहायता से बनाए गए हैं।'


def clean_tags(tags):
    result=[]
    seen=set()
    for value in tags:
        tag=' '.join(value.strip().lstrip('#').split())
        if not tag or len(tag)>40 or tag.casefold() in seen:
            continue
        cost=sum(len(t)+(2 if ' ' in t else 0)+1 for t in result+[tag])
        if cost<=480:
            result.append(tag)
            seen.add(tag.casefold())
    return result


def prepare_packaging(root,story):
    identity=hashlib.sha256(json.dumps(dict(version=VERSION,summary=story['summary'],
        scenes=story['scenes']),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path=Path(root)/'seo-package.json'
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved.get('identity')!=identity:
        schema=object_schema({'title':string(20,90),'description':string(250,1600),
            'tags':{'type':'array','minItems':8,'maxItems':12,'items':string(2,40)}})
        package=ask(schema,
            'Package this original Hindi fictional story for relevant YouTube search and an honest click. '
            'Do not change the story. Title: lead with the specific conflict/choice in clear Hindi, '
            'then ONE natural search phrase such as Hindi Story, Emotional Hindi Story or Motivational Kahani. '
            'Keep under 90 characters. No fake true-story, viral, celebrity, guaranteed success or cure claims. '
            'Description: first two lines describe this actual story conflict and who it resonates with; '
            'naturally use the strongest relevant Hindi and Romanized Hindi search phrase. Follow with a concise '
            'original synopsis without spoiling the resolution and a specific lesson grounded in the ending. '
            'No keyword lists, repeated keyword stuffing, invented timestamps, external links, hashtags or credits. '
            'Tags: 8-12 distinct short relevant phrases; mix Hindi Devanagari, Romanized Hindi and English. '
            'Prioritize the actual theme/setting and search intent, then Hindi story/category phrases. '
            'No music, kids rhyme, unrelated celebrity or trending tags. No invented search-volume claims. '
            'Current working title: '+story['title']+' Summary: '+story['summary']+
            '\nFinal Hindi script: '+story['lyrics'],
            int(identity[:7],16),2400,checkpoint=Path(root)/'seo-response.json')
        tags=clean_tags(package['tags'])
        if len(tags)<6:
            raise ValueError('Insufficient distinct story-specific SEO tags')
        package['tags']=tags
        package['description']=package['description'].strip()+'\n\n'+DISCLOSURE+'\n#HindiStory #MotivationalStory'
        saved=dict(identity=identity,version=VERSION,package=package)
        save_json(path,saved)
    for field in ('title','description','tags'):
        story[field]=saved['package'][field]
