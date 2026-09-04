#!/usr/bin/env python3
"""Create a reviewable seven-day Candy batch; never publish or approve it."""
import argparse, json, os, re, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from candy_cloud import ROOT, TZ, CloudError, load_campaign

SLOTS = ((11, 'A'), (15, 'A'), (19, 'B'))
CAPTIONS = (
    'Round {n}: Can you get all three? 🍭 #trivia #quiztok #mobilegames #iphone',
    'Round {n}: Three questions. One perfect score. 🍬 #trivia #quiztok #braingames #iphone',
    'Round {n}: Most players miss the last one. 🍭 #trivia #quiztok #mobilegames #challenge',
)

def response_text(payload):
    for item in payload.get('output', []):
        for part in item.get('content', []):
            if part.get('type') == 'output_text': return part['text']
    raise CloudError('CONTENT_RESPONSE_MISSING')

def generate(count=21, min_future_days=10):
    posts = load_campaign(); now = datetime.now(TZ)
    latest = max(datetime.fromisoformat(p['scheduled_at']).astimezone(TZ) for p in posts.values())
    if (latest.date() - now.date()).days >= min_future_days:
        print('Content coverage is sufficient; no batch created.'); return []
    existing = [p['data'][s]['question'] for p in posts.values() for s in ('q1','q2','q3')]
    needed=count*3
    schema={'type':'object','properties':{'facts':{'type':'array','minItems':needed,'maxItems':needed,'items':{'type':'object','properties':{'question':{'type':'string'},'answer':{'type':'string'},'source_url':{'type':'string'}},'required':['question','answer','source_url'],'additionalProperties':False}}},'required':['facts'],'additionalProperties':False}
    prompt=f"Create {needed} short, evergreen general-trivia question/answer pairs for a family-friendly TikTok quiz. Verify every answer with web search and give its direct reputable source URL. Avoid trick questions, disputed facts, current officeholders, and these existing questions: {json.dumps(existing)}"
    body={'model':os.getenv('CANDY_CONTENT_MODEL','gpt-5.6-luna'),'tools':[{'type':'web_search'}],'input':prompt,'text':{'format':{'type':'json_schema','name':'candy_facts','strict':True,'schema':schema}}}
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise CloudError('MISSING_OPENAI_API_KEY')
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+api_key,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=600) as r: facts=json.loads(response_text(json.load(r)))['facts']
    seen={' '.join(x.casefold().split()) for x in existing}; outputs=[]; next_day=max(p['number'] for p in posts.values())+1; start=latest.date()+timedelta(days=1)
    for i in range(count):
        qs=facts[i*3:i*3+3]
        for q in qs:
            n=' '.join(q['question'].casefold().split())
            if (n in seen or not re.match(r'https://', q['source_url'])
                    or not (5 <= len(q['question']) <= 100) or not (1 <= len(q['answer']) <= 45)):
                raise CloudError('INVALID_OR_DUPLICATE_GENERATED_FACT')
            seen.add(n)
        hour,template=SLOTS[i%3]; when=datetime.combine(start+timedelta(days=i//3),datetime.min.time(),TZ).replace(hour=hour)
        data={'day':next_day+i,'q1':{k:qs[0][k] for k in ('question','answer')},'q2':{k:qs[1][k] for k in ('question','answer')},'q3':{**{k:qs[2][k] for k in ('question','answer')},'withhold':True},'caption':CAPTIONS[i%3].format(n=next_day+i),'scheduledAt':when.isoformat(),'meta':{'calendarDay':i//3+1,'slot':i%3+1,'format':'weekly-reviewed','goal':'growth','sources':[q['source_url'] for q in qs]},'visualTemplate':template}
        path=ROOT/'examples'/'auto'/f'post-{next_day+i:03d}.json'
        if path.exists():
            raise CloudError('GENERATED_POST_ALREADY_EXISTS')
        outputs.append((path, data))
    written=[]
    try:
        for path, data in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            written.append(path)
        load_campaign()
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise
    print(f'Created {len(written)} review-only posts.'); return written

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--posts',type=int,default=21); p.add_argument('--min-future-days',type=int,default=10); a=p.parse_args(); generate(a.posts,a.min_future_days)
