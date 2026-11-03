"""Check every planned composition with both pinned production CLIP tokenizers."""
import os

from transformers import CLIPTokenizer
from authored_song import load_authored_song
from music_short import companion
from music_video import image_plan, planned_timeline
from story_art_style import focused_prompt
from story_image_cpu import MODEL, REVISION, safer_prompt


def verify(identity):
    tokenizers=[CLIPTokenizer.from_pretrained(MODEL,revision=REVISION,subfolder=key,token=False)
                for key in ('tokenizer','tokenizer_2')]
    song=load_authored_song(identity); checked=0; maximum=0
    for value in (song,companion(song,'readiness')):
        for index in range(len(planned_timeline(value)['slots'])):
            for kind in ('background','thumbnail'):
                plan=image_plan(value,{},index,kind)
                for attempt in range(4):
                    for suffix in ('',' Fully clothed, nonviolent scene, preserve the described action and setting.'):
                        def count(text):
                            return max(len(t(safer_prompt(text+suffix),truncation=False,verbose=False)['input_ids'])
                                       for t in tokenizers)
                        prompt=focused_prompt(plan['contract'],kind,attempt,token_count=count)
                        length=count(prompt)
                        if length>77 or 'faces visible' not in prompt.lower():
                            raise ValueError('Production music prompt lost its face requirement or exceeded CLIP context')
                        checked+=1;maximum=max(maximum,length)
    print(f'PASS: {checked} real CLIP context checks; largest prompt {maximum}/77 tokens',flush=True)


if __name__=='__main__':verify(os.getenv('AUTHORED_SONG','ab-baat-karein-2026-11-03'))
