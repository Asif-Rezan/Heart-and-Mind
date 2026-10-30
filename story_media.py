"""Shared streaming hashes and bounded FFmpeg calls for story assets."""
import hashlib
from pathlib import Path
import subprocess


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def run_ffmpeg(args):
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y',*args],check=True,capture_output=True)
