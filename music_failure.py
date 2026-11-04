"""Small public diagnostics; never serialize generated prose, API errors or secrets."""
import datetime as dt
import json
import os
from pathlib import Path
import re

from pipeline import pipeline_failure_message


def save_failure(run_id, stage, error):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',run_id):
        return
    root=Path('output')/run_id
    root.mkdir(parents=True,exist_ok=True)
    message=pipeline_failure_message(error)
    code=re.search(r'\[([a-z_]+)\]',message)
    report=dict(run_id=run_id,stage=stage,status='failed',error_type=type(error).__name__,
        code=code[1] if code else 'generation_failed',message=message,
        has_audio=(root/'song.wav').exists(),has_video=(root/'video.mp4').exists(),
        resume='Use the same run_id and set prepared_run to this GitHub run ID.',
        recorded_at=dt.datetime.now(dt.timezone.utc).isoformat())
    try:
        quality=json.loads((root/'lyrics-quality.json').read_text())
    except (OSError,ValueError):
        quality={}
    if type(quality.get('word_count')) is int:
        report['lyric_word_count']=quality['word_count']
    report['lyric_attempts_exhausted']=quality.get('attempts_exhausted') is True
    target=root/'generation-failure.json'
    temp=target.with_suffix('.tmp')
    temp.write_text(json.dumps(report,indent=2))
    temp.replace(target)
    return report


def summarize():
    lines=['### Generation recovery diagnostics']
    for path in Path('output').glob('*/generation-failure.json'):
        report=json.loads(path.read_text())
        lines.extend([f"- Run: `{report['run_id']}`; stage: `{report['stage']}`; code: `{report['code']}`.",
                      f"- {report['message']}",
                      f"- Saved audio: {report['has_audio']}; saved video: {report['has_video']}.",
                      f"- {report['resume']}"])
        if 'lyric_word_count' in report:
            lines.append(f"- Sung words: {report['lyric_word_count']}; required range: 160–235.")
    if len(lines)==1:
        lines.append('Failure occurred before a generation checkpoint; inspect the failed setup/check step.')
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as output:
        output.write('\n'.join(lines)+'\n')


if __name__=='__main__':
    summarize()
