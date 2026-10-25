"""Generate through the requested official ACE-Step 1.5 Hugging Face Space."""
import os
import subprocess
from pathlib import Path
from gradio_client import Client

SPACE = 'ACE-Step/Ace-Step-v1.5'

def generate(song, target, state, save):
    if state.get('generation_started'):
        raise RuntimeError('Ambiguous Space generation; reconcile before resubmission')
    client = Client(SPACE, token=os.getenv('HF_TOKEN') or None, download_files=str(target.parent/'space-downloads'), verbose=False)
    info = client.view_api(return_format='dict', print_info=False)
    endpoint = info['named_endpoints']['/generation_wrapper']
    parameters = endpoint['parameters']
    values = {p['parameter_name']: p.get('parameter_default') for p in parameters}
    # Resolve by the public endpoint's labels; refuse an incompatible deployment.
    wanted = {'models': 'acestep-v15-turbo', 'Song Description': '',
        'Prompt': song['prompt'], 'Lyrics': song['lyrics'], 'Vocal Language': 'hi',
        'Vocal Language (optional)': 'hi', 'Audio Duration (seconds)': song['duration'],
        'batch size': 1, 'Audio Format': 'flac', 'Thinking': False}
    found = set()
    for p in parameters:
        label = p.get('label')
        if label in wanted:
            choices = p.get('type', {}).get('enum')
            if choices and wanted[label] not in choices:
                raise RuntimeError('Official Space does not support requested ' + label)
            values[p['parameter_name']] = wanted[label]
            found.add(label)
    if not {'models', 'Thinking', 'Prompt', 'Lyrics', 'Audio Duration (seconds)', 'Vocal Language', 'Audio Format'} <= found:
        raise RuntimeError('Official Space endpoint changed; review its API before generation')
    # The official generation_wrapper inputs 37-39 are the metadata,
    # caption and language CoT switches. Disabling Thinking alone still
    # invokes its 5Hz LM when any of these are enabled (upstream inference.py).
    for name in ('param_37', 'param_38', 'param_39'):
        parameter = next((p for p in parameters if p['parameter_name'] == name), None)
        if not parameter or parameter.get('type', {}).get('type') != 'boolean':
            raise RuntimeError('Official Space planning controls changed; review the API')
        values[name] = False
    values['generation_mode'] = 'custom'
    state['generation_started'] = True
    save()
    try:
        result = client.predict(**values, api_name='/generation_wrapper')
    except Exception as error:
        from gradio_client.exceptions import AppError
        # This exact terminal service response confirms the task stopped.
        # Transport failures and timeouts stay ambiguous and cannot resubmit.
        if isinstance(error, AppError) and str(error).strip().startswith('You have exceeded your ZeroGPU runs limit.'):
            state['generation_started'] = False
            state['generation_failed'] = 'ZeroGPU quota exhausted before generation'
            save()
            raise RuntimeError('ACE-Step ZeroGPU quota exhausted; configure HF_TOKEN with available quota or a private ACESTEP_API_URL') from None
        if isinstance(error, AppError) and str(error).strip() == 'GPU task aborted':
            state['generation_started'] = False
            state['generation_failed'] = 'GPU task aborted'
            save()
            raise RuntimeError('ACE-Step hosted GPU task aborted; saved lyrics can be resumed') from None
        raise
    audio = result[0]
    if isinstance(audio, dict):
        audio = audio.get('path')
    if not isinstance(audio, str) or not Path(audio).is_file():
        raise RuntimeError('Official Space returned no generated audio')
    from pipeline import duration, validate_duration
    validate_duration(duration(Path(audio)))
    temporary = target.with_name(target.stem + '.converting.wav')
    subprocess.run(['ffmpeg', '-y', '-i', audio, '-map', '0:a:0', '-vn',
        '-c:a', 'pcm_s16le', str(temporary)], check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    validate_duration(duration(temporary))
    temporary.replace(target)
    state['audio_ready'] = True
    save()
