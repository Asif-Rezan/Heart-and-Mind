"""Run Qwen3-4B-Instruct-2507 locally; no hosted text API or credentials."""
import copy
import hashlib
import json
import os
from pathlib import Path
import time

from jsonschema import Draft202012Validator, ValidationError
from story_constraints import is_hindi_word_pattern, is_hindi_cta_pattern

MODEL_ID = 'Qwen/Qwen3-4B-Instruct-2507'
GGUF_REPO = 'unsloth/Qwen3-4B-Instruct-2507-GGUF'
GGUF_REVISION = 'a06e946bb6b655725eafa393f4a9745d460374c9'
GGUF_FILE = 'Qwen3-4B-Instruct-2507-Q4_K_M.gguf'
GGUF_SHA256 = '3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
CONTEXT_TOKENS = 16384
_model = None


class StoryGenerationError(RuntimeError):
    """Only static, privacy-safe messages may be emitted in public job logs."""
    def __init__(self,message,code='story_model_runtime_failure',details=None):
        super().__init__(message)
        self.code=code
        self.details=details or {}
        self.public_message=message


def verify_model(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == GGUF_SHA256


def load_model():
    global _model
    if _model is not None:
        return _model
    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama
    for attempt in range(3):
        try:
            path = hf_hub_download(repo_id=GGUF_REPO, filename=GGUF_FILE,
                revision=GGUF_REVISION, token=False, force_download=attempt > 0)
            if not verify_model(path):
                raise StoryGenerationError('Qwen model checksum verification failed')
            break
        except Exception:
            if attempt == 2:
                raise StoryGenerationError('Qwen model download or checksum failed after three attempts') from None
            print(json.dumps({'check': 'Qwen model download retry', 'attempt': attempt + 1}), flush=True)
            time.sleep(2 ** (attempt + 1))
    threads = min(max(1, int(os.getenv('OMP_NUM_THREADS', '4'))), os.cpu_count() or 1)
    try:
        _model = Llama(model_path=path, n_ctx=CONTEXT_TOKENS, n_threads=threads,
            n_threads_batch=threads, n_gpu_layers=0, n_batch=256, use_mmap=True,
            chat_format='chatml', verbose=False)
    except Exception:
        raise StoryGenerationError('Qwen CPU runtime could not load the verified model') from None
    print(json.dumps({'check': 'Qwen CPU model loaded', 'model': MODEL_ID,
        'quantization': 'Q4_K_M', 'threads': threads}), flush=True)
    return _model


def request_story(endpoint, payload):
    if endpoint != 'chat/completions':
        raise StoryGenerationError('Qwen supports lyrics JSON generation only')
    if payload.get('model', MODEL_ID) != MODEL_ID or os.getenv('LYRICS_MODEL', MODEL_ID) != MODEL_ID:
        raise StoryGenerationError('LYRICS_MODEL must be Qwen/Qwen3-4B-Instruct-2507')
    schema = payload.get('response_format', {}).get('json_schema', {}).get('schema')
    if not isinstance(schema, dict):
        raise StoryGenerationError('Lyrics generation requires an explicit JSON schema')
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    messages = copy.deepcopy(payload['messages'])
    messages.append({'role': 'user', 'content': 'Return only JSON matching this schema. '
        'Do not add commentary or markdown. JSON Schema: ' + json.dumps(schema)})
    limit = int(payload.get('max_completion_tokens', 4200))
    if not 1 <= limit <= 6000:
        raise StoryGenerationError('Lyrics output token budget must be between 1 and 6000')
    # Bounds remain enforced by jsonschema. Expanding thousands of optional
    # characters in llama.cpp's grammar can overflow its native parser stack.
    grammar_schema = copy.deepcopy(schema)
    def remove_string_bounds(node):
        if isinstance(node, dict):
            node.pop('minLength', None)
            node.pop('maxLength', None)
            # Only our small, bounded Hindi word grammar is safe in the native parser.
            if node.get('pattern') == r'^[^\u0900-\u097f]*[A-Za-z][^\u0900-\u097f]*$':
                # A simple ASCII subset enforces English planning during decoding,
                # avoiding the large Unicode negated ranges in the original pattern.
                node['pattern'] = r'^[ -~]*[A-Za-z][ -~]*$'
            elif not (is_hindi_word_pattern(node.get('pattern')) or is_hindi_cta_pattern(node.get('pattern'))):
                node.pop('pattern', None)
            for value in node.values():
                remove_string_bounds(value)
        elif isinstance(node, list):
            for value in node:
                remove_string_bounds(value)
    remove_string_bounds(grammar_schema)
    seed = payload.get('seed', 1700)
    if type(seed) is not int or not 0 <= seed <= 2**31 - 3:
        raise StoryGenerationError('Lyrics seed must be a nonnegative 31-bit integer')
    model = load_model()
    for attempt in range(3):
        # Retry feedback also consumes context; recheck before every inference.
        prompt_tokens = sum(len(model.tokenize(message['content'].encode(), add_bos=False)) + 16
                            for message in messages) + 32
        if prompt_tokens + limit > CONTEXT_TOKENS:
            raise StoryGenerationError('Qwen context budget exceeded; reduce recent-story context')
        started = time.monotonic()
        try:
            result = model.create_chat_completion(messages=messages,
                response_format={'type': 'json_object', 'schema': grammar_schema},
                max_tokens=limit, temperature=max(.2, float(payload.get('temperature', .7)) - .15 * attempt),
                top_p=.8, top_k=20, repeat_penalty=1.05, seed=seed + attempt)
        except Exception:
            # Runtime/configuration errors are not content errors; don't spin on them.
            raise StoryGenerationError('Qwen CPU generation failed; inspect runner memory and runtime compatibility') from None
        issue, field, bound = None, '$', None
        failed_pattern = None
        try:
            choice = result['choices'][0]
            if choice.get('finish_reason') != 'stop':
                issue = 'incomplete_output'
                raise ValueError('Incomplete output')
            validator.validate(json.loads(choice['message']['content']))
        except ValidationError as error:
            issue = error.validator
            failed_pattern = error.schema.get('pattern')
            path = list(error.absolute_path)
            if path and path[0] in schema.get('properties', {}):
                field = '.'.join(str(part) for part in path)
            if isinstance(error.validator_value, int):
                bound = error.validator_value
        except (ValueError, TypeError, KeyError, IndexError):
            issue = issue or 'invalid_json_or_response'
        if issue:
            # Report schema constraints and counters, never generated content or raw errors.
            print(json.dumps({'check': 'Qwen JSON validation retry', 'attempt': attempt + 1,
                'constraint': issue, 'field': field, 'bound': bound,
                'completion_tokens': result.get('usage', {}).get('completion_tokens')}), flush=True)
            if attempt == 2:
                raise StoryGenerationError('Qwen returned incomplete or invalid lyrics JSON after three attempts',code='story_model_response_invalid',
                    details=dict(constraint=issue,field=field,bound=bound,attempt_limit=3)) from None
            correction = f'The previous response failed {issue} for field {field}.'
            if bound is not None:
                correction += f' The required {issue} is {bound}.'
            if issue == 'pattern' and failed_pattern == r'^[^\u0900-\u097f]*[A-Za-z][^\u0900-\u097f]*$':
                correction += (f' Field {field} must be English only, with Latin-letter names and NO Devanagari. '
                    'Write summary, characters, world and every chapters entry in English. '
                    'Only title, description and spoken text use Hindi. Keep the English planning concise.')
            if issue == 'pattern' and is_hindi_word_pattern(failed_pattern):
                correction += ' Spoken Hindi must follow the exact word range in its schema: single spaces, Devanagari words, no quotations or ASCII numbers. Shorten overloaded lines or expand short lines; do not repeat the rejected wording. Do not append exposition.'
            if issue == 'pattern' and is_hindi_cta_pattern(failed_pattern):
                correction += ' The closing line must start with आप, ask a story-specific Hindi question, and end exactly with ? टिप्पणी में बताइए। within the word limit.'
            if issue == 'incomplete_output':
                correction += ' Shorten prose and lyric lines so the entire JSON fits the output budget.'
            messages.append({'role': 'user', 'content': correction +
                ' Regenerate the complete JSON matching the supplied schema. Follow every field length limit. '
                'Every spoken text or lyrics field must be Hindi Devanagari; thumbnail_text and image prompts must follow '
                'their own ASCII/English rules. Do not add fields or commentary.'})
            continue
        print(json.dumps({'check': 'Qwen lyrics JSON', 'passed': True,
            'seconds': round(time.monotonic() - started, 1),
            'prompt_tokens': result.get('usage', {}).get('prompt_tokens',prompt_tokens),
            'completion_tokens': result.get('usage', {}).get('completion_tokens')}), flush=True)
        return result
