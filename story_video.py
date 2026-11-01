"""Select the preserved background renderer or the Python 2D puppet renderer.

STORY_VIDEO_STYLE=auto (default), puppet or background. A saved selection follows
artifacts through later stages, so local resume does not silently switch modes.
"""
import importlib
from pathlib import Path
from story_writer import save_json
from story_puppet_video import visual_timeline, thumbnail_slot, validate_timing, FPS


from story_video_style import video_style


def backend(root):
    style=video_style(root)
    return importlib.import_module('story_puppet_video' if style=='puppet' else 'story_background_video')


def generate_images(root,story,render_ready=False):
    style=video_style(root)
    save_json(Path(root)/'video-style.json',dict(style=style))
    return backend(root).generate_images(root,story,render_ready=render_ready)


def render_clips(root,*args,**kwargs):
    return backend(root).render_clips(root,*args,**kwargs)


def render(root,*args,**kwargs):
    return backend(root).render(root,*args,**kwargs)


def render_identity(root,*args,**kwargs):
    return backend(root).render_identity(root,*args,**kwargs)


def clip_identity(root,*args,**kwargs):
    return backend(root).clip_identity(root,*args,**kwargs)


def clip_is_current(root,*args,**kwargs):
    return backend(root).clip_is_current(root,*args,**kwargs)
