import argparse
import json
from pathlib import Path
import re
from asmr.plan import atomic
from .writer import write,validate_song
from . import publication as pub

def run(args):
 if not re.fullmatch(r'english-song-[A-Za-z0-9_-]{1,60}',args.run_id):raise ValueError('Invalid English song run ID')
 root=Path('output')/args.run_id;root.mkdir(parents=True,exist_ok=True);pub.preflight()
 if args.stage=='restore':return pub.restore(root,args.run_id,media=not args.metadata_only)
 if args.stage=='lyrics':
  song=write(root,args.run_id,args.seconds,args.voice,pub.history(),args.topic);pub.reserve(song);return song
 song=validate_song(json.loads((root/'song.json').read_text()))
 if args.stage in ('music','image','assemble'):
  from . import media
  if args.stage=='image':return media.image(root,song,args.index)
  return getattr(media,args.stage)(root,song)
 return getattr(pub,args.stage)(root,song)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True)
 parser.add_argument('--stage',required=True,choices=['lyrics','music','image','assemble','backup','publish','cleanup','restore'])
 parser.add_argument('--seconds',type=int,choices=[180,210,240,270,300],default=210)
 parser.add_argument('--voice',choices=['female','male'],default='female')
 parser.add_argument('--topic',default='Original emotional pop / soft-pop')
 parser.add_argument('--index',type=int);parser.add_argument('--metadata-only',action='store_true');args=parser.parse_args()
 try:run(args)
 except Exception as error:
  record=dict(stage=args.stage,error_type=type(error).__name__)
  if re.fullmatch(r'english-song-[A-Za-z0-9_-]{1,60}',args.run_id):atomic(Path('output')/args.run_id/'failure.json',record)
  print(json.dumps(record),flush=True);raise SystemExit(1)
