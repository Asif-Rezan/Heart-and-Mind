"""Explicit ASMR decoding grammar; never silently fall back to generic JSON."""
import json
from .plan import MATERIALS, PALETTES, SHAPES, PATTERNS


def grammar_text():
 def enum(values):
  return ' | '.join(json.dumps(json.dumps(v)) for v in values)
 scenes=' ws "," ws '.join(['scene']*12)
 tags=' ws "," ws '.join(['string']*5)+' (ws "," ws string){0,7}'
 return '\n'.join([
  'root ::= "{" ws "\\\"idea\\\"" ws ":" ws string ws "," ws "\\\"video\\\"" ws ":" ws metadata ws "," ws "\\\"shorts\\\"" ws ":" ws metadata ws "," ws "\\\"scenes\\\"" ws ":" ws "[" ws '+scenes+' ws "]" ws "," ws "\\\"short_scenes\\\"" ws ":" ws "[" ws index ws "," ws index ws "," ws index ws "]" ws "}" ws',
  'metadata ::= "{" ws "\\\"title\\\"" ws ":" ws string ws "," ws "\\\"description\\\"" ws ":" ws string ws "," ws "\\\"tags\\\"" ws ":" ws "[" ws '+tags+' ws "]" ws "}"',
  'scene ::= "{" ws "\\\"label\\\"" ws ":" ws string ws "," ws "\\\"material\\\"" ws ":" ws material ws "," ws "\\\"palette\\\"" ws ":" ws palette ws "," ws "\\\"shape\\\"" ws ":" ws shape ws "," ws "\\\"pattern\\\"" ws ":" ws pattern ws "," ws "\\\"cuts\\\"" ws ":" ws cuts ws "}"',
  'material ::= '+enum(MATERIALS), 'palette ::= '+enum(PALETTES),
  'shape ::= '+enum(SHAPES),'pattern ::= '+enum(PATTERNS),
  'cuts ::= "8" | "9" | "10"',
  'index ::= "0" | "1" | "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "10" | "11"',
  r'string ::= "\"" char* "\""',
  r'char ::= [^"\\\x00-\x1F] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4})',
  r'ws ::= [ \t\n\r]{0,4}',
 ])


def ask(prompt,spec,seed):
 from llama_cpp import LlamaGrammar
 from lyrics_cpu import load_model,inference_progress,CONTEXT_TOKENS
 model=load_model()
 messages=[dict(role='system',content='Design original procedural ASMR episodes. Return the complete requested JSON only.'),
  dict(role='user',content=prompt+'\nJSON Schema: '+json.dumps(spec))]
 tokens=sum(len(model.tokenize(m['content'].encode(),add_bos=False))+16 for m in messages)+32
 if tokens+4800>CONTEXT_TOKENS:raise ValueError('ASMR model context exceeded')
 # Passing grammar directly avoids the chat adapter's schema-to-JSON fallback.
 grammar=LlamaGrammar.from_string(grammar_text(),verbose=False)
 print(json.dumps(dict(check='ASMR strict grammar inference',prompt_tokens=tokens)),flush=True)
 with inference_progress():
  response=model.create_chat_completion(messages=messages,grammar=grammar,max_tokens=4800,
   temperature=.55,top_p=.8,top_k=20,repeat_penalty=1.05,seed=seed)
 choice=response['choices'][0]
 if choice.get('finish_reason')!='stop':raise ValueError('ASMR model output incomplete')
 return json.loads(choice['message']['content'])
