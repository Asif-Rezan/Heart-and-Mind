"""Opt-in real Qwen CPU regression; unit tests alone cannot verify native grammar."""
import json
from pathlib import Path
from story_constraints import hindi_word_pattern
from story_writer import ask, object_schema, string, save_json


def main():
    root=Path('output/story-word-bound-regression')
    schema=object_schema({'text':dict(string(1,400),pattern=hindi_word_pattern(4,8))})
    result=ask(schema,
        'Write a complete Hindi sentence about a father opening his son’s notebook. '
        'Try to write exactly twenty-five words, but the JSON schema takes precedence. '
        'Use Devanagari Hindi and single spaces.',113,320,checkpoint=root/'adversarial-response.json')
    words=len(result['text'].split())
    assert 4<=words<=8, 'Native grammar did not enforce the Hindi word cap'
    # Reproduce the failed shared headroom: a 161-word script and two 15-word
    # beats have only four words of growth, allocated as two per beat.
    schema=object_schema({f'scene_{i}':object_schema({
        'text':dict(string(20,400),pattern=hindi_word_pattern(4,17))}) for i in (4,6)})
    response=ask(schema,
        'Rewrite two chronological Hindi story beats about Ravi balancing study and work with his father. '
        'Scene 4: a teacher asks why Ravi missed class. Scene 6: Ravi returns home and studies in his notebook. '
        'Write naturally connected narration in Hindi Devanagari. Try to explain each beat in thirty words, '
        'but the exact JSON schema word ranges take precedence. Use single spaces.',114,650,
        checkpoint=root/'shared-budget-response.json')
    counts=[len(row['text'].split()) for row in response.values()]
    assert all(4<=n<=17 for n in counts)
    total=161-30+sum(counts)
    assert 120<=total<=165
    save_json(root/'validation.json',dict(passed=True,real_cpu_model=True,
        adversarial_words=words,batch_words=counts,story_total=total))


if __name__=='__main__':main()
