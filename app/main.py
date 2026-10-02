from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import json, re, os, math, uuid
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'data' / 'people.json').read_text(encoding='utf-8'))
BY_ID = {p['id']: p for p in DATA}
CUSTOM = {}
app = FastAPI(title='Pairwise — Agentic Dating')
templates = Jinja2Templates(directory=str(ROOT / 'app' / 'templates'))
app.mount('/static', StaticFiles(directory=str(ROOT / 'app' / 'static')), name='static')

STOP = set('the and for with that this from into about have has are was were your their they them you our of to a an in on is as at by or be it its we i me my'.split())

def tokens(p):
    vals = p.get('interests', []) + p.get('hobbies', []) + p.get('values', []) + [p.get('role', '')]
    words = set()
    for x in vals:
        words |= {w.lower() for w in re.findall(r'[a-zA-Z][a-zA-Z-]+', x) if w.lower() not in STOP}
    return words

def overlap_items(a, b):
    ta, tb = tokens(a), tokens(b)
    shared = sorted(ta & tb)
    return shared

def compatibility(a, b):
    shared = overlap_items(a, b)
    ta, tb = tokens(a), tokens(b)
    union = max(1, len(ta | tb))
    overlap = len(shared) / union
    role_bonus = 0.06 if any(x in ta for x in ['technology', 'entrepreneurship', 'startups', 'ai']) and any(x in tb for x in ['technology', 'entrepreneurship', 'startups', 'ai']) else 0
    style_pairs = {
        ('curious', 'conversational'): 0.05, ('reflective', 'thoughtful'): 0.04,
        ('technical', 'product-focused'): 0.05, ('creative', 'expressive'): 0.05,
        ('mission-driven', 'collaborative'): 0.05, ('analytical', 'idea-driven'): 0.04,
        ('energetic', 'ambitious'): 0.04, ('strategic', 'analytical'): 0.04,
        ('calm', 'reflective'): 0.04, ('technical', 'future-focused'): 0.04,
    }
    sa = a.get('style', '').split(',')[0].strip(); sb = b.get('style', '').split(',')[0].strip()
    style_bonus = style_pairs.get((sa, sb), style_pairs.get((sb, sa), 0))
    score = round(min(0.97, max(0.48, 0.58 + 0.30 * overlap + role_bonus + style_bonus)), 2)
    return score, shared[:8]

def fit_reason(a, b, shared):
    shared = shared[:3]
    if not shared:
        return 'Different profiles, but enough adjacent interests to make the conversation worth testing.'
    bits = [f'shared {x}' for x in shared]
    return 'Strongest overlap: ' + ', '.join(bits) + '. Their profiles also show complementary interests, giving the agents something specific to explore.'

def friction(a, b, shared):
    ai, bi = set(a.get('interests', [])), set(b.get('interests', []))
    a_only = list(ai - bi); b_only = list(bi - ai)
    if a_only and b_only:
        return f"Different emphasis: {a['name']} signals {a_only[0]}, while {b['name']} signals {b_only[0]}. That could create either curiosity or friction."
    return 'The available sources do not show a major obvious mismatch; the agents would need another conversation to learn more.'

def get_person(pid):
    return BY_ID.get(pid) or CUSTOM.get(pid)

def profile_view(p):
    return {
        **p,
        'source_policy': 'Only the supplied public LinkedIn and public Instagram URLs are used for this profile. Unestablished traits are not filled in as facts.',
        'evidence': [f"LinkedIn: {p['linkedin']}", f"Instagram: {p['instagram']}"],
        'needs': [
            f"Signals point toward {', '.join(p['values'][:2])}",
            f"Enjoys {p['hobbies'][0]} and conversations around {p['interests'][0]}"
        ],
        'agent_brief': f"{p['style'].capitalize()}. The agent will prioritize conversations around {', '.join(p['interests'][:3])} and probe for real-world compatibility rather than relying on a single shared keyword."
    }

def make_conversation(a, b, shared):
    shared = shared or ['curiosity']
    a_interest = a.get('interests', ['their work'])[0]
    b_interest = b.get('interests', ['their work'])[0]
    a_hobby = a.get('hobbies', ['free time'])[0]
    b_hobby = b.get('hobbies', ['free time'])[0]
    a_value = a.get('values', ['what matters to them'])[0]
    b_value = b.get('values', ['what matters to them'])[0]
    common = shared[0]
    return [
        {'speaker': a['name'], 'role': 'agent-a', 'text': f"I noticed your profile leans toward {b_interest}, while mine has a strong signal around {a_interest}. What keeps you genuinely interested in it?"},
        {'speaker': b['name'], 'role': 'agent-b', 'text': f"For me, it becomes interesting when it turns into something practical. I also spend time on {b_hobby}, so I like switching between focused work and something completely different."},
        {'speaker': a['name'], 'role': 'agent-a', 'text': f"That makes sense. We both have a signal around {common}. If we had an afternoon with no work obligations, would you rather explore that interest together or do something neither of us normally does?"},
        {'speaker': b['name'], 'role': 'agent-b', 'text': f"I'd probably explore it, but I care about {b_value}. I like conversations where there is a real idea underneath the activity, not just filling time."},
        {'speaker': a['name'], 'role': 'agent-a', 'text': f"Interesting. My profile also points to {a_value}. One difference I noticed is that you seem more drawn to {b_interest}, while I spend more time around {a_interest}. Would that difference make the conversation better or harder?"},
        {'speaker': b['name'], 'role': 'agent-b', 'text': f"Probably better if there is curiosity on both sides. I'd rather learn why someone sees something differently than agree on everything. That's usually where a useful conversation starts."},
    ]

def date_for(a, b):
    score, shared = compatibility(a, b)
    conv = make_conversation(a, b, shared)
    shared_text = shared or ['curiosity']
    dimensions = {
        'Shared interests': min(96, 60 + len(shared) * 7),
        'Conversation fit': min(95, int(67 + score * 27)),
        'Values overlap': min(94, int(64 + score * 29)),
        'Complementarity': min(93, int(61 + (1 - min(0.65, len(shared) / 10)) * 32 + (score - .48) * 15)),
    }
    return {
        'a': a, 'b': b, 'score': score, 'shared': shared_text,
        'conversation': conv,
        'summary': fit_reason(a, b, shared),
        'friction': friction(a, b, shared),
        'next_date': f"Ask about {b.get('hobbies', ['their interests'])[0]} and {a.get('values', ['what matters to them'])[0]} next.",
        'dimensions': dimensions,
        'method': 'The date is generated from the two stored source profiles: shared interests drive the opening, values shape the deeper questions, and differences create a compatibility probe.'
    }

def rankings(person_id):
    me = get_person(person_id)
    if not me: return []
    rows = []
    for p in DATA:
        if p['id'] == person_id: continue
        s, shared = compatibility(me, p)
        rows.append({
            'person': p,
            'score': round(s * 100),
            'shared': shared,
            'reason': fit_reason(me, p, shared),
            'friction': friction(me, p, shared)
        })
    rows.sort(key=lambda x: x['score'], reverse=True)
    for i, r in enumerate(rows): r['rank'] = i + 1
    return rows

def fetch_public(url):
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; PairwiseDemo/1.0)'}
    try:
        r = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        desc = ''
        m = soup.find('meta', attrs={'name': 'description'})
        if m: desc = m.get('content', '')
        return {'ok': r.ok, 'title': title[:180], 'description': desc[:500], 'status': r.status_code}
    except Exception as e:
        return {'ok': False, 'title': '', 'description': '', 'status': 0, 'error': str(e)}

def new_profile(linkedin, instagram):
    ln = fetch_public(linkedin); ig = fetch_public(instagram)
    text = (ln.get('title', '') + ' ' + ln.get('description', '') + ' ' + ig.get('title', '') + ' ' + ig.get('description', '')).lower()
    interest_map = {
        'technology': ['technology'], 'ai': ['AI', 'technology'], 'startup': ['entrepreneurship', 'startups'],
        'design': ['design'], 'music': ['music'], 'fitness': ['fitness'], 'travel': ['travel'],
        'finance': ['finance', 'investing'], 'writing': ['writing'], 'education': ['education']
    }
    interests = []
    for key, vals in interest_map.items():
        if key in text: interests += vals
    interests = list(dict.fromkeys(interests))[:6] or ['Not enough public-source signal']
    name = 'New profile'
    m = re.search(r'^(.*?)\s+[|–-]', ln.get('title', ''))
    if m: name = m.group(1).strip()
    return {
        'id': 'custom', 'name': name, 'role': 'Analyzed from public-source metadata',
        'linkedin': linkedin, 'instagram': instagram, 'interests': interests,
        'hobbies': ['Not established from the supplied sources'],
        'style': 'Not established from the supplied sources',
        'values': ['Not established from the supplied sources'], 'live': True,
        'linkedin_snapshot': ln, 'instagram_snapshot': ig
    }

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse('index.html', {'request': request, 'people': DATA})

@app.get('/profiles', response_class=HTMLResponse)
def profiles(request: Request):
    return templates.TemplateResponse('profiles.html', {'request': request, 'people': DATA})

@app.get('/profile/{pid}', response_class=HTMLResponse)
def profile(request: Request, pid: str):
    p = get_person(pid)
    if not p: return HTMLResponse('Not found', status_code=404)
    return templates.TemplateResponse('profile.html', {'request': request, 'p': profile_view(p)})

@app.get('/date/{a}/{b}', response_class=HTMLResponse)
def date_page(request: Request, a: str, b: str):
    pa, pb = get_person(a), get_person(b)
    if not pa or not pb or a == b: return HTMLResponse('Not found', status_code=404)
    d = date_for(pa, pb)
    return templates.TemplateResponse('date.html', {'request': request, 'd': d})

@app.get('/rankings/{pid}', response_class=HTMLResponse)
def rank_page(request: Request, pid: str):
    me = get_person(pid)
    if not me: return HTMLResponse('Not found', status_code=404)
    return templates.TemplateResponse('rankings.html', {'request': request, 'me': me, 'rows': rankings(pid)})

@app.post('/api/analyze')
async def analyze(payload: dict):
    linkedin = (payload.get('linkedin') or '').strip(); instagram = (payload.get('instagram') or '').strip()
    if not linkedin or not instagram: return JSONResponse({'error': 'Both public URLs are required.'}, status_code=400)
    if 'linkedin.com' not in linkedin.lower() or 'instagram.com' not in instagram.lower():
        return JSONResponse({'error': 'Please provide a LinkedIn URL and an Instagram URL.'}, status_code=400)
    p = new_profile(linkedin, instagram)
    p['id'] = 'custom-' + uuid.uuid4().hex[:10]
    CUSTOM[p['id']] = p
    result = profile_view(p)
    result['profile_url'] = f'/profile/{p["id"]}'
    result['ranking_url'] = f'/rankings/{p["id"]}'
    return JSONResponse(result)

@app.post('/api/date')
async def api_date(payload: dict):
    a = payload.get('a'); b = payload.get('b')
    pa, pb = get_person(a), get_person(b)
    if not pa or not pb or a == b: return JSONResponse({'error': 'Unknown profile'}, status_code=404)
    return JSONResponse(date_for(pa, pb))

@app.get('/api/rankings/{pid}')
def api_rank(pid: str):
    p = get_person(pid)
    if not p: return JSONResponse({'error': 'Unknown profile'}, status_code=404)
    return JSONResponse({'person': p, 'rankings': rankings(pid)})
