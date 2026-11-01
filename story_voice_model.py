"""Pinned, anonymous CPU Hindi narration models; no external inference service."""
import os

GOONJ_MODEL='BH-Builds/goonj-1-82M'
GOONJ_REVISION='7056ccc1a0b58beaad09fe2057730545d74261cb'
GOONJ_VOICES=('hi_ravi','hi_atul','hi_meera','hi_shivani')
KOKORO_MODEL='hexgrad/Kokoro-82M'


def voice_profile(engine=None,voice=None,legacy=False):
    engine='kokoro' if legacy else engine or os.getenv('STORY_VOICE_ENGINE','goonj')
    voice=('hm_omega' if legacy else voice or os.getenv('STORY_NARRATOR_VOICE') or
           ('hi_ravi' if engine=='goonj' else 'hm_omega'))
    if engine=='goonj' and voice in GOONJ_VOICES:
        return dict(engine=engine,model=GOONJ_MODEL,revision=GOONJ_REVISION,voice=voice)
    if engine=='kokoro' and voice in ('hm_omega','hm_psi','hf_alpha','hf_beta'):
        return dict(engine=engine,model=KOKORO_MODEL,voice=voice)
    raise ValueError('Unsupported Hindi narration engine or stock voice')


def load_pipeline(profile):
    import torch
    from kokoro import KModel,KPipeline
    if profile['engine']=='kokoro':
        return KPipeline(lang_code='h',device='cpu',repo_id=KOKORO_MODEL),profile['voice']
    from huggingface_hub import hf_hub_download
    def download(filename):
        return hf_hub_download(repo_id=GOONJ_MODEL,revision=GOONJ_REVISION,filename=filename,token=False)
    model=KModel(repo_id=KOKORO_MODEL,config=download('config.json'),model=download('kokoro_hindi_final.pth')).to('cpu').eval()
    voice=torch.load(download(f"voices/{profile['voice']}.pt"),map_location='cpu',weights_only=True)
    if tuple(voice.shape)!=(510,1,256) or not torch.isfinite(voice).all():
        raise RuntimeError('Invalid Hindi stock voice pack')
    pipeline=KPipeline(lang_code='h',device='cpu',repo_id=KOKORO_MODEL,model=model)
    return pipeline,voice
