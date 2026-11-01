"""Small Hindi word grammars, kept bounded for the CPU JSON decoder."""
import re

MAX_GRAMMAR_WORDS = 48


def hindi_word_pattern(minimum, maximum):
    if not 1 <= minimum <= maximum <= MAX_GRAMMAR_WORDS:
        raise ValueError('Unsupported Hindi word bounds')
    return rf'^[ऀ-ॿ]+([,!?]? [ऀ-ॿ]+){{{minimum-1},{maximum-1}}}[।!?]?$'


def is_hindi_word_pattern(pattern):
    if not isinstance(pattern, str):
        return False
    match = re.fullmatch(r'\^\[ऀ-ॿ\]\+\(\[,!\?\]\? \[ऀ-ॿ\]\+\)\{(\d+),(\d+)\}\[।!\?\]\?\$', pattern)
    return bool(match and 0 <= int(match[1]) <= int(match[2]) < MAX_GRAMMAR_WORDS)


def edit_word_limits(story, indices):
    """Allocate shared headroom once, so a whole accepted batch stays in budget."""
    from story_format import word_bounds
    minimum, maximum = word_bounds(story)
    total = sum(len(s['text'].split()) for s in story['scenes'])
    growth = max(0, maximum-total)//len(indices)
    shrink = max(0, total-minimum)//len(indices)
    limits = {}
    for i in indices:
        current = len(story['scenes'][i]['text'].split())
        upper = min(MAX_GRAMMAR_WORDS, current+growth)
        lower = min(upper, max(4, current-shrink))
        limits[i] = dict(current_words=current, minimum_words=lower, maximum_words=upper)
    return limits


def constrain_edits(schema, limits):
    for i, bounds in limits.items():
        schema['properties'][f'scene_{i}']['properties']['text']['pattern'] = hindi_word_pattern(
            bounds['minimum_words'], bounds['maximum_words'])
    return schema
