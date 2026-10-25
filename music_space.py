"""Generate through the requested official ACE-Step 1.5 Hugging Face Space."""
import json
import shutil
from pathlib import Path
from gradio_client import Client

SPACE = 'ACE-Step/Ace-Step-v1.5'

def generate(song, target, state, save):
    if state.get('generation_started'):
        raise RuntimeError('Ambiguous Space generation; reconcile before resubmission')
    client = Client(SPACE, download_files=str(target.parent/'space-downloads'), verbose=False)
    info = client.view_api(return_format='dict', print_info=False)
    endpoint = info['named_endpoints']['/generation_wrapper']
    parameters = endpoint['parameters']
    values = {p['parameter_name']: p.get('parameter_default') for p in parameters}
    # Resolve by the public endpoint's labels; refuse an incompatible deployment.
    wanted = {'models': 'acestep-v15-xl-turbo', 'Song Description': '',
        'Prompt': song['prompt'], 'Lyrics': song['lyrics'], 'Vocal Language': 'hi',
        'Vocal Language (optional)': 'hi', 'Audio Duration (seconds)': song['duration'],
        'batch size': 1, 'Audio Format': 'wav', 'Thinking': True}
    found = set()
    for p in parameters:
        label = p.get('label')
        if label in wanted:
            values[p['parameter_name']] = wanted[label]
            found.add(label)
    if not {'Prompt', 'Lyrics', 'Audio Duration (seconds)', 'Vocal Language'} <= found:
        raise RuntimeError('Official Space endpoint changed; review its API before generation')
    values['generation_mode'] = 'custom'
    state['generation_started'] = True
    save()
    result = client.predict(**values, api_name='/generation_wrapper')
    audio = result[0]
    if isinstance(audio, dict):
        audio = audio.get('path')
    if not isinstance(audio, str) or not Path(audio).is_file():
        raise RuntimeError('Official Space returned no generated audio')
    from pipeline import duration, validate_duration
    validate_duration(duration(Path(audio)))
    shutil.copyfile(audio, target)
    state['audio_ready'] = True
    save()
