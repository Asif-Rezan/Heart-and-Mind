"""Explicit ASMR decoding grammar; never silently fall back to generic JSON."""
import json
from .plan import ACTIVITIES, PALETTES, SHAPES, PATTERNS


def grammar_text(metadata_only=False,activities=None):
 def literal(value):return json.dumps(json.dumps(value))
 def enum(values):return ' | '.join(literal(v) for v in values)
 def object_rule(fields):
  return '\"{\" ws '+' ws \",\" ws '.join(literal(key)+' ws \":\" ws '+value for key,value in fields)+' ws \"}\"'
 scenes=' ws \",\" ws '.join(['scene']*12)
 tags=' ws \",\" ws '.join(['string']*5)+' (ws \",\" ws string){0,7}'
 rules=[
  'root ::= '+('metadata ws' if metadata_only else object_rule([('idea','string'),('video','metadata'),('shorts','metadata'),('scenes','\"[\" ws '+scenes+' ws \"]\"'),('short_scenes','\"[\" ws index ws \",\" ws index ws \",\" ws index ws \"]\"')])+' ws'),
  'metadata ::= '+object_rule([('title','string'),('description','string'),('tags','\"[\" ws '+tags+' ws \"]\"')]),
  'scene ::= '+' | '.join(a+'-scene' for a in (activities or ACTIVITIES)),
  'palette ::= '+enum(PALETTES),'shape ::= '+enum(SHAPES),'pattern ::= '+enum(PATTERNS),
  'cycles ::= \"8\" | \"9\" | \"10\"',
  'index ::= '+' | '.join(json.dumps(str(i)) for i in range(12)),
  r'string ::= "\"" char* "\""',
  r'char ::= [^"\\\x00-\x1F] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})',
  r'ws ::= [ \t\n\r]{0,4}',
 ]
 for activity in (activities or ACTIVITIES):
  rules.append(activity+'-material ::= '+enum(ACTIVITIES[activity]))
  rules.append(activity+'-scene ::= '+object_rule([('label','string'),('activity',literal(activity)),('material',activity+'-material'),('palette','palette'),('shape','shape'),('pattern','pattern'),('cycles','cycles')]))
 return '\n'.join(rules)


def ask(prompt,spec,seed):
 from llama_cpp import LlamaGrammar
 from lyrics_cpu import load_model,inference_progress,CONTEXT_TOKENS
 model=load_model()
 messages=[dict(role='system',content='Design original procedural ASMR episodes. Return the complete requested JSON only.'),
  dict(role='user',content=prompt+'\nJSON Schema: '+json.dumps(spec))]
 tokens=sum(len(model.tokenize(m['content'].encode(),add_bos=False))+16 for m in messages)+32
 if tokens+4800>CONTEXT_TOKENS:raise ValueError('ASMR model context exceeded')
 # Passing grammar directly avoids the chat adapter's schema-to-JSON fallback.
 grammar=LlamaGrammar.from_string(grammar_text(metadata_only=set(spec.get('properties',{}))=={'title','description','tags'},activities=spec.get('properties',{}).get('scenes',{}).get('items',{}).get('properties',{}).get('activity',{}).get('enum')),verbose=False)
 print(json.dumps(dict(check='ASMR strict grammar inference',prompt_tokens=tokens)),flush=True)
 with inference_progress():
  response=model.create_chat_completion(messages=messages,grammar=grammar,max_tokens=4800,
   temperature=.55,top_p=.8,top_k=20,repeat_penalty=1.05,seed=seed)
 choice=response['choices'][0]
 if choice.get('finish_reason')!='stop':raise ValueError('ASMR model output incomplete')
 return json.loads(choice['message']['content'])
