"""Restore separate Actions artifacts in dependency order, never download order."""
import argparse
import json
from pathlib import Path
import re
import shutil

STAGES = ('outline', 'chapter', 'prose', 'planning', 'input', 'voice', 'score',
          'images', 'mix', 'video', 'publication', 'cleanup')


def restore_artifacts(source, destination, run_id):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id):
        raise ValueError('Invalid story run identity')
    ordered = []
    for artifact in Path(source).iterdir():
        match = re.match(r'story-('+'|'.join(STAGES)+r')-\d+(?:-|$)', artifact.name)
        if not artifact.is_dir() or not match:
            continue
        root = artifact/run_id
        if not root.is_dir():
            continue
        ordered.append((STAGES.index(match[1]), artifact.name, root))
    if not ordered:
        raise ValueError('No matching saved story artifacts; check prepared_run and run_id')
    target = Path(destination)/run_id
    restored = []
    for _, name, root in sorted(ordered):
        for identity_file in ('story-draft.json', 'story-prose.json', 'story.json'):
            path = root/identity_file
            if path.exists() and json.loads(path.read_text()).get('run_id') != run_id:
                raise ValueError('Saved artifact story identity mismatch')
        shutil.copytree(root, target, dirs_exist_ok=True)
        restored.append(name)
    print(json.dumps(dict(phase='story checkpoints restored in dependency order',artifacts=restored)),flush=True)
    return restored


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', default='output')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    restore_artifacts(args.source, args.destination, args.run_id)
