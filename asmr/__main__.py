"""Production and credential-free preview CLI."""
import argparse
import json
from pathlib import Path
import re
from .plan import atomic,generate,validate_plan,metadata

def run(args):
 if not re.fullmatch(r'asmr-[A-Za-z0-9_-]{1,70}',args.run_id):raise ValueError('Invalid ASMR run ID')
 root=Path('output')/args.run_id;root.mkdir(parents=True,exist_ok=True)
 from . import publication as pub
 pub.preflight()
 if args.stage=='restore':return pub.restore(root,args.run_id,media=not args.metadata_only)
 if args.stage=='plan':
  plan=generate(root,args.run_id,args.seconds,pub.load_history())
  pub.reserve(plan)
  atomic(root/'video-metadata.json',metadata(plan,'video'))
  atomic(root/'short-metadata.json',metadata(plan,'shorts'))
  print(json.dumps(dict(run_id=args.run_id,seconds=plan['seconds'],scenes=len(plan['scenes']),fingerprint=plan['fingerprint'],publish=pub.publish_enabled())),flush=True)
  return plan
 plan=validate_plan(json.loads((root/'plan.json').read_text()))
 if args.stage=='scene':
  if args.index is None or not 0<=args.index<12:raise ValueError('ASMR scene index must be 0-11')
  from .render import render_scene
  return render_scene(root,plan['scenes'][args.index])
 if args.stage=='assemble':
  from .render import assemble
  return assemble(root,plan)
 if args.stage=='backup':return pub.backup(root,plan)
 if args.stage=='youtube':return pub.publish_youtube(root,plan)
 if args.stage=='facebook':return pub.publish_facebook(root,plan)
 if args.stage=='cleanup':return pub.cleanup(root,plan)
 raise ValueError('Unknown ASMR stage')

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--run-id',required=True)
 parser.add_argument('--seconds',type=int,choices=[240,270,300],default=270)
 parser.add_argument('--stage',required=True,choices=['plan','scene','assemble','backup','youtube','facebook','cleanup','restore'])
 parser.add_argument('--index',type=int)
 parser.add_argument('--metadata-only',action='store_true')
 args=parser.parse_args()
 try:run(args)
 except Exception as error:
  # API exception strings and bodies can contain credentials; log types only.
  record=dict(stage=args.stage,error_type=type(error).__name__)
  if re.fullmatch(r'asmr-[A-Za-z0-9_-]{1,70}',args.run_id):atomic(Path('output')/args.run_id/'failure.json',record)
  print(json.dumps(record),flush=True)
  raise SystemExit(1)

if __name__=='__main__':main()
