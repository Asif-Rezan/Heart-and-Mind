"""Conservative written-Hindi phrasing checks, not an acoustic rhythm score.

Schwa deletion and sung vowel stretching depend on pronunciation/melody. The
estimated vowel weight below only catches grossly uneven phrases for revision.
"""
import hashlib
import re
import unicodedata

class LyricQualityError(ValueError):
    pass


VERSION = 3
ORDER = ['Verse 1', 'Pre-Chorus', 'Chorus', 'Verse 2', 'Chorus', 'Bridge', 'Final Chorus', 'Outro']
COUNTS = [4, 2, 4, 4, 4, 2, 4, 2]
GUIDE = '''Write a romantic/emotional Hindi album song about affection, longing,
separation, reunion, trust or healing after lost love. Never turn it into a motivational
speech. Choose ONE emotional relationship and one form of address, तुम or तू.
Use natural spoken Hindi with poetic feeling, not literal English translation.
Structure exactly: [Verse 1] 4 lines, [Pre-Chorus] 2, [Chorus] 4,
[Verse 2] 4, [Chorus] repeat EXACTLY, [Bridge] 2, [Final Chorus] repeat EXACTLY,
[Outro] 2. No Intro, instrumental prose or unlabelled directions.
Aim 6-9 words per line, 180-220 sung words including repeated choruses.
Compose each line as a breathable two-bar phrase in the supplied 4/4 tempo.
Use comparable spoken vowel lengths within each section and match corresponding
Verse 1/Verse 2 lines so the same melody can fit both. Count pronunciation, not
just words. Allow a natural held final vowel; never rush extra words into a bar.
Use a natural paired end-rhyme or near-rhyme in verses and chorus, without
breaking grammar or repeating the same last word merely to fake a rhyme.
The chorus needs a specific memorable emotional hook, not a generic title chant.
Verse 1 establishes an intimate moment; Verse 2 changes the relationship;
the bridge admits a feeling or makes a decision. Avoid sermon-like life advice,
random imagery and strings of दिल/जान/प्यार with no meaningful statement.
All sung text must be Devanagari. Keep English section labels in brackets.'''


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()


def vowel_weight(line):
    """Approximate written vowel units; intentionally not claimed as exact matra."""
    total = 0
    for word in re.findall(r'[\u0900-\u097f]+', unicodedata.normalize('NFC', line)):
        for i, char in enumerate(word):
            after = word[i+1:i+2]
            if '\u0915' <= char <= '\u0939' or '\u0958' <= char <= '\u095f':
                # Ignore nukta when looking for a vowel sign or virama.
                if after == '़': after = word[i+2:i+3]
                total += 0 if after == '्' else 2 if after in 'ाीूेैोौ' and after else 1
            elif char in 'अइउऋ': total += 1
            elif char in 'आईऊएऐओऔ': total += 2
    return total


def assess(text):
    # Older completions place the first sung line beside its section label.
    text_layout = re.sub(r'(?m)^[ \t]*(\[[^\]\n]+\])[ \t]+([^\n]+)$', r'\1\n\2', text)
    sections = []
    issues = []
    for raw in text_layout.splitlines():
        line = raw.strip()
        if not line: continue
        if re.fullmatch(r'\[[^\]]+\]', line):
            sections.append((line[1:-1], []))
        elif not sections:
            issues.append('Sung text before the first section')
        else:
            sections[-1][1].append(line)
    if [s[0] for s in sections] != ORDER:
        issues.append('Use the exact eight-section song structure')
    metrics = []
    for index, (name, lines) in enumerate(sections):
        words = [len(re.findall(r'[\u0900-\u097f]+', line)) for line in lines]
        weights = [vowel_weight(line) for line in lines]
        metrics.append(dict(section=name, words=words, estimated_vowel_units=weights))
        if index < len(COUNTS) and len(lines) != COUNTS[index]:
            issues.append(f'{name}: expected {COUNTS[index]} sung lines')
        if any(re.search(r'[A-Za-z]', line) for line in lines):
            issues.append(f'{name}: use Devanagari sung words only')
        if any(n < 4 or n > 10 for n in words):
            issues.append(f'{name}: phrase too short or overloaded; aim 6-9 words')
        if any(n < 8 or n > 36 for n in weights) or (weights and max(weights)-min(weights) > 7):
            issues.append(f'{name}: uneven estimated vowel lengths {weights}; revise for balanced phrases')
    if [s[0] for s in sections] == ORDER:
        if sections[2][1] != sections[4][1] or sections[2][1] != sections[6][1]:
            issues.append('All three chorus performances must use identical words')
        if len(sections[0][1]) == len(sections[3][1]) == 4:
            if any(abs(vowel_weight(a)-vowel_weight(b)) > 6 for a,b in zip(sections[0][1],sections[3][1])):
                issues.append('Corresponding verse lines need compatible phrase lengths for the same melody')
        verse_lines = sections[0][1]+sections[3][1]
        if len(set(verse_lines)) < 6:
            issues.append('Verses repeat filler instead of developing the relationship')
    word_count = sum(sum(m['words']) for m in metrics)
    if not 160 <= word_count <= 235:
        issues.append(f'Total sung words {word_count}; target 180-220')
    return dict(version=VERSION, lyrics_hash=fingerprint(text), passed=not issues,
                issues=issues, word_count=word_count, sections=metrics,
                limitation='Written phrasing heuristic; melody, pronunciation and perceived emotion require listening review.')


def review(request, lyrics, genre, bpm, voice, attempt=0):
    """Separate model critique of meaning/rhyme; fallible, not human approval."""
    criteria = ['coherent_relationship', 'natural_hindi', 'natural_rhyme', 'singable_phrasing']
    schema = dict(type='object', additionalProperties=False, required=criteria+['issues'],
        properties={**{key:dict(type='boolean') for key in criteria},
                    'issues':dict(type='array',maxItems=6,items=dict(type='string',minLength=1,maxLength=220))})
    prompt = f'''Review these original Hindi lyrics critically; do not rewrite them.
    Genre {genre}; {bpm} BPM, 4/4, solo {voice} narrator.
    Judge each boolean honestly. coherent_relationship: meaningful romantic/emotional
    relationship with a clear situation and progression, no motivational sermon or
    random metaphors. natural_hindi: idiomatic grammar, consistent pronouns/gender.
    natural_rhyme: audible natural end-rhyme/near-rhyme, not identical word filler.
    singable_phrasing: comparable spoken syllable lengths, natural stresses and breath
    points for two-bar phrases; no crammed prose. Written counts alone cannot prove this.
    For every false criterion give a specific section/line and concrete revision reason
    in issues. Do not approve merely because the JSON/structure is correct.
    Lyrics:\n{lyrics}'''
    result = request(prompt, schema, 1600, 200+attempt)
    return dict(passed=all(result[key] for key in criteria) and not result['issues'],
                **result, reviewer='same-model-critique-not-human-or-audio-verification')


SECTION_KEYS = [('verse_1',4), ('pre_chorus',2), ('chorus',4), ('verse_2',4), ('bridge',2), ('outro',2)]


def section_schema():
    """Constrain unique stanzas during decoding; chorus copies are rendered locally."""
    return dict(type='object', additionalProperties=False,
        required=[key for key,_ in SECTION_KEYS],
        properties={key:dict(type='array',minItems=count,maxItems=count,
            items=dict(type='string',minLength=12,maxLength=110,
                       pattern=r'^[^\r\n\[\]]*[\u0900-\u097f][^\r\n\[\]]*$'))
                    for key,count in SECTION_KEYS})


def parse_sections(text):
    """Read historical drafts without losing lyrics beside an inline heading."""
    result = {}
    names = dict(zip(['Verse 1','Pre-Chorus','Chorus','Verse 2','Bridge','Outro'],
                     [key for key,_ in SECTION_KEYS]))
    key = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        label = re.match(r'^\[([^\]]+)\]\s*(.*)$', line)
        if label:
            name, line = label.groups()
            key = names.get(name)
            # Only the first chorus is needed; subsequent repetitions are canonical.
            if key in result: key = None
            if key: result[key] = []
        if key and line: result[key].append(line)
    return result


def render_sections(sections):
    order = [('Verse 1','verse_1'),('Pre-Chorus','pre_chorus'),('Chorus','chorus'),
             ('Verse 2','verse_2'),('Chorus','chorus'),('Bridge','bridge'),
             ('Final Chorus','chorus'),('Outro','outro')]
    return '\n\n'.join('['+label+']\n'+'\n'.join(sections[key]) for label,key in order)
