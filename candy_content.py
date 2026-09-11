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

def request_json(prompt, schema, name):
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        raise CloudError('MISSING_OPENAI_API_KEY')
    body = {
        'model': os.getenv('CANDY_CONTENT_MODEL', 'gpt-5.6-luna'),
        'tools': [{'type': 'web_search'}],
        'input': prompt,
        'text': {'format': {'type': 'json_schema', 'name': name, 'strict': True, 'schema': schema}},
    }
    req = urllib.request.Request(
        'https://api.openai.com/v1/responses', data=json.dumps(body).encode(),
        headers={'Authorization': 'Bearer ' + api_key, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as response:
        return json.loads(response_text(json.load(response)))

def fact_checks(facts):
    count = len(facts)
    item = {
        'type': 'object',
        'properties': {
            'index': {'type': 'integer'},
            'question_answer_match': {'type': 'boolean'},
            'answer_factually_supported': {'type': 'boolean'},
            'source_supports_answer': {'type': 'boolean'},
            'corrected_question': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
            'corrected_answer': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
            'corrected_source_url': {'anyOf': [{'type': 'string'}, {'type': 'null'}]},
        },
        'required': ['index', 'question_answer_match', 'answer_factually_supported', 'source_supports_answer',
                     'corrected_question', 'corrected_answer', 'corrected_source_url'],
        'additionalProperties': False,
    }
    schema = {
        'type': 'object',
        'properties': {'checks': {'type': 'array', 'minItems': count, 'maxItems': count, 'items': item}},
        'required': ['checks'],
        'additionalProperties': False,
    }
    numbered = [{'index': i, **fact} for i, fact in enumerate(facts)]
    prompt = (
        'Independently fact-check every trivia item below. Use web search and inspect the supplied source. '
        'question_answer_match is true only when the answer directly and unambiguously answers that exact '
        'question. answer_factually_supported is true only when reliable evidence confirms it. '
        'source_supports_answer is true only when the supplied URL supports the stated answer. For a failed '
        'item, supply a corrected question, answer, and direct reputable source URL. For a passing item, set '
        f'all corrected fields to null. Return every index. Items: {json.dumps(numbered)}')
    return request_json(prompt, schema, 'candy_fact_checks').get('checks', [])

def checks_pass(checks, count):
    return ({check.get('index') for check in checks} == set(range(count))
            and all(all(check.get(field) for field in (
                'question_answer_match', 'answer_factually_supported', 'source_supports_answer'))
                for check in checks))

def verify_question_answers(facts):
    checks = fact_checks(facts)
    if checks_pass(checks, len(facts)):
        return facts
    if {check.get('index') for check in checks} != set(range(len(facts))):
        raise CloudError('QUESTION_ANSWER_VERIFICATION_FAILED')
    corrected = [dict(fact) for fact in facts]
    for check in checks:
        if all(check.get(field) for field in (
                'question_answer_match', 'answer_factually_supported', 'source_supports_answer')):
            continue
        replacement = {
            'question': check.get('corrected_question'),
            'answer': check.get('corrected_answer'),
            'source_url': check.get('corrected_source_url'),
        }
        if (not all(isinstance(value, str) and value.strip() for value in replacement.values())
                or not re.match(r'https://', replacement['source_url'])
                or not (5 <= len(replacement['question']) <= 100)
                or not (1 <= len(replacement['answer']) <= 45)):
            raise CloudError('QUESTION_ANSWER_AUTOCORRECT_FAILED')
        corrected[check['index']] = replacement
    if not checks_pass(fact_checks(corrected), len(corrected)):
        raise CloudError('QUESTION_ANSWER_AUTOCORRECT_FAILED')
    return corrected

def generate(count=21, min_future_days=10):
    posts = load_campaign(); now = datetime.now(TZ)
    latest = max(datetime.fromisoformat(p['scheduled_at']).astimezone(TZ) for p in posts.values())
    if (latest.date() - now.date()).days >= min_future_days:
        print('Content coverage is sufficient; no batch created.'); return []
    existing = [p['data'][s]['question'] for p in posts.values() for s in ('q1','q2','q3')]
    needed=count*3
    schema={'type':'object','properties':{'facts':{'type':'array','minItems':needed,'maxItems':needed,'items':{'type':'object','properties':{'question':{'type':'string'},'answer':{'type':'string'},'source_url':{'type':'string'}},'required':['question','answer','source_url'],'additionalProperties':False}}},'required':['facts'],'additionalProperties':False}
    prompt=f"Create {needed} short, evergreen general-trivia question/answer pairs for a family-friendly TikTok quiz. Verify every answer with web search and give its direct reputable source URL. Avoid trick questions, disputed facts, current officeholders, and these existing questions: {json.dumps(existing)}"
    facts = request_json(prompt, schema, 'candy_facts')['facts']
    seen={' '.join(x.casefold().split()) for x in existing}; outputs=[]; next_day=max(p['number'] for p in posts.values())+1; start=latest.date()+timedelta(days=1)
    for i in range(count):
        qs=facts[i*3:i*3+3]
        for q in qs:
            n=' '.join(q['question'].casefold().split())
            if (n in seen or not re.match(r'https://', q['source_url'])
                    or not (5 <= len(q['question']) <= 100) or not (1 <= len(q['answer']) <= 45)):
                raise CloudError('INVALID_OR_DUPLICATE_GENERATED_FACT')
            seen.add(n)
    facts = verify_question_answers(facts)
    seen={' '.join(x.casefold().split()) for x in existing}
    for q in facts:
        n=' '.join(q['question'].casefold().split())
        if (n in seen or not re.match(r'https://', q['source_url'])
                or not (5 <= len(q['question']) <= 100) or not (1 <= len(q['answer']) <= 45)):
            raise CloudError('INVALID_OR_DUPLICATE_AUTOCORRECTED_FACT')
        seen.add(n)
    for i in range(count):
        qs=facts[i*3:i*3+3]
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
