"""Hindi text boundaries; internal visual prompts stay English for the pinned image model."""
import re
import unicodedata

LANGUAGE = 'hi'
WORD = f'[{chr(0x0900)}-{chr(0x0963)}{chr(0x0971)}-{chr(0x097f)}]+'
LYRIC_PATTERN = '^' + WORD + '( ' + WORD + '){3,11}[।!?]?$'


def normalized(text):
    return ' '.join(re.findall(r'[a-z0-9\u0900-\u0963\u0971-\u097f]+',
                               unicodedata.normalize('NFC', text).casefold()))


def require_hindi(text, field='text'):
    clean = text.replace('Heart and Mind', '').replace('#Shorts', '')
    if (not re.search(r'[\u0900-\u097f]', clean)
            or any(c.isalpha() and not '\u0900' <= c <= '\u097f' for c in clean)):
        raise ValueError('Hindi Devanagari required: ' + field)
    return text


def validate_generated_text(value):
    """Validate public/sung fields while leaving image descriptions in English."""
    if 'lyric' in value:
        require_hindi(value['lyric'], 'lyric')
    if 'verses' in value:
        for row in value['verses']:
            require_hindi(row['lyric'], 'lyric')
    if 'chorus' in value:
        for line in value['chorus']:
            require_hindi(line, 'chorus')
    if 'chapters' in value:
        for field in ('title', 'description', 'story_summary'):
            require_hindi(value[field], field)
        for chapter in value['chapters']:
            require_hindi(chapter, 'chapter')
    if 'video' in value and 'shorts' in value:
        for title in value['title_candidates']:
            require_hindi(title, 'title candidate')
        for kind in ('video', 'shorts'):
            for field in ('title', 'description'):
                require_hindi(value[kind][field], kind + ' ' + field)
    return value


def validate_song_language(song):
    if song.get('language') != LANGUAGE:
        raise ValueError('New Heart and Mind episodes require language hi')
    for field in ('title', 'description', 'lyrics'):
        require_hindi(song[field], field)
    return song


def motion_hint(text):
    hints = []
    for words, action in [(['ताली','तालियाँ'], 'clap hands'), (['कूद','उछल'], 'jump'),
                          (['घूम','घुम'], 'spin'), (['हिलो','झूम','नाच'], 'dance')]:
        if any(word in text for word in words):
            hints.append(action)
    return ' '.join(hints)
