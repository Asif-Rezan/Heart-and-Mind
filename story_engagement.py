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


def polish_engagement(root,story):
    """Review the assembled story as one arc; repair only flagged narrative beats."""
    root=Path(root)
    identity=hashlib.sha256(json.dumps(story['scenes'],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    path=root/'engagement-review.json'
    saved=json.loads(path.read_text()) if path.exists() else {}
    if saved.get('identity')==identity:
        story['scenes']=saved['scenes']
        story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
        if saved.get('approved'):
            return
    review_schema=object_schema({**{key:{'type':'boolean'} for key in ('hook','progression','payoff','cta')},
        'repairs':{'type':'array','maxItems':6,'items':object_schema({
            'scene':{'type':'integer','minimum':0,'maximum':47},'instruction':string(10,240)})}})
    for attempt in range(3):
        review=ask(review_schema,
            'Act as a strict Hindi short-story editor. Audit the actual script, not its intentions. '
            'Hook: first two scenes present a concrete dilemma/open question without greetings or spoiler. '
            'Progression: causal choices, escalating stakes, new information every few beats; no recaps or repeated lines. '
            'Payoff: ending resolves the opening question through an earned emotional consequence, not a sermon. '
            'CTA: AFTER the resolution, one brief specific reflective comment question and at most one gentle follow invitation. '
            'No manipulation or repeated subscription requests. If any criterion fails, identify up to six exact scene '
            'indices with actionable repair instructions. Keep the story original, credible and coherent. '
            'Mark true only when the actual script satisfies that criterion. Final script: '+
            json.dumps(story['scenes'],ensure_ascii=False),
            int(identity[:7],16)+attempt,1600,checkpoint=root/f'engagement-audit-{attempt}.json')
        approved=all(review[key] for key in ('hook','progression','payoff','cta'))
        save_json(path,dict(identity=identity,scenes=story['scenes'],review=review,approved=approved))
        if approved:
            return
        if attempt==2 or not review['repairs']:
            break
        instructions={row['scene']:row['instruction'] for row in review['repairs']}
        schema=object_schema({f'scene_{i}':object_schema({'text':string(20,400),'visual':string(20,360)}) for i in instructions})
        response=ask(schema,
            'Revise ONLY these story beats to satisfy the editor. Each text is 11-15 natural Hindi words, '
            'one narrator; no repeated line, no new character or changed canonical event. Keep a complete 4-6 minute arc. '
            'Update each English visual to reflect the revised text and same cast/location. '
            'Keep calls to action only at the very end after the emotional payoff. Canonical cast: '+story['characters']+
            '\nFull script: '+json.dumps(story['scenes'],ensure_ascii=False)+
            '\nRepairs: '+json.dumps(instructions,ensure_ascii=False),
            int(identity[:7],16)+attempt+100,3200,checkpoint=root/f'engagement-repair-{attempt}.json')
        for i in instructions:
            value=response[f'scene_{i}']
            if speech_issues(value['text']):
                raise ValueError('Invalid Hindi engagement edit')
            story['scenes'][i]=dict(value,index=i,speaker='narrator')
        story['lyrics']='\n'.join(s['text'] for s in story['scenes'])
        save_json(path,dict(identity=identity,scenes=story['scenes'],review=review,approved=False))
    raise ValueError('Story hook/progression/payoff/CTA review did not pass; preserve script for review')
