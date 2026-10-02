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
    interests = [x for x in p.get('interests', []) if x]
    hobbies = [x for x in p.get('hobbies', []) if x]
    values = [x for x in p.get('values', []) if x]
    quality = p.get('source_quality', {})

    if values:
        need_line = f"Signals point toward {', '.join(values[:2])}."
    else:
        need_line = "The supplied pages did not expose enough evidence to infer personal values."

    enjoy_line = (
        f"Enjoys {', '.join(hobbies[:2]) or 'activities not established'} "
        f"and conversations around {', '.join(interests[:2]) or 'topics not established'}."
    )

    if interests:
        brief = (
            f"{p.get('style', 'Evidence-limited')}. "
            f"The agent will prioritize conversations around {', '.join(interests[:3])} "
            "and probe for real-world compatibility rather than treating weak metadata as fact."
        )
    else:
        brief = (
            "Evidence-limited. The agent will ask discovery questions instead of inventing "
            "interests, hobbies, values, or personality traits."
        )

    return {
        **p,
        'source_policy': (
            'Only the supplied public LinkedIn and public Instagram URLs are used for this profile. '
            'Weak or missing signals are shown as unknown rather than invented.'
        ),
        'evidence': [
            f"LinkedIn: {p['linkedin']} · {quality.get('LinkedIn', 'supplied')}",
            f"Instagram: {p['instagram']} · {quality.get('Instagram', 'supplied')}"
        ],
        'needs': [need_line, enjoy_line],
        'agent_brief': brief,
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

def normalize_url(url):
    url = (url or '').strip()
    if not re.match(r'^https?://', url, re.I):
        url = 'https://' + url
    return url

def source_host(url):
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().split(':')[0].replace('www.', '')
    except Exception:
        return ''

def slug_name(url):
    try:
        from urllib.parse import urlparse
        parts = [x for x in urlparse(url).path.split('/') if x]
        if not parts:
            return ''
        slug = parts[-1]
        if slug.lower() in {'about', 'profile', 'me'} and len(parts) > 1:
            slug = parts[-2]
        slug = re.sub(r'[^A-Za-z0-9._-]+', '', slug).strip('._-')
        if not slug:
            return ''
        words = re.sub(r'[_._-]+', ' ', slug).split()
        return ' '.join(w.capitalize() for w in words)
    except Exception:
        return ''

def _meta(soup, *keys):
    for attr, value in keys:
        tag = soup.find('meta', attrs={attr: value})
        if tag and tag.get('content'):
            return tag.get('content', '').strip()
    return ''

def _jsonld_text(soup):
    chunks = []
    for tag in soup.find_all('script', attrs={'type': re.compile(r'application/ld\+json', re.I)}):
        raw = tag.string or tag.get_text(' ', strip=True)
        if not raw:
            continue
        try:
            obj = json.loads(raw)
            objs = obj if isinstance(obj, list) else [obj]
            for item in objs:
                if not isinstance(item, dict):
                    continue
                for key in ('name', 'headline', 'description', 'jobTitle', 'worksFor', 'about'):
                    value = item.get(key)
                    if isinstance(value, dict):
                        value = value.get('name', '')
                    if isinstance(value, list):
                        value = ' '.join(str(v) for v in value)
                    if value:
                        chunks.append(str(value))
        except Exception:
            pass
    return ' '.join(chunks)

def _visible_text(soup):
    for tag in soup(['script', 'style', 'noscript', 'svg']):
        tag.decompose()
    return re.sub(r'\s+', ' ', soup.get_text(' ', strip=True))[:8000]

def _parse_html(html, final_url, status=200):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    og_title = _meta(soup, ('property', 'og:title'), ('name', 'twitter:title'))
    desc = _meta(
        soup,
        ('name', 'description'),
        ('property', 'og:description'),
        ('name', 'twitter:description')
    )
    canonical = soup.find('link', rel='canonical')
    canonical_url = canonical.get('href', '').strip() if canonical else final_url
    jsonld = _jsonld_text(soup)
    visible = _visible_text(soup)
    combined = ' '.join(x for x in [title, og_title, desc, jsonld, visible] if x)

    blocked_markers = (
        'sign in', 'join linkedin', 'log in', 'login', 'challenge',
        'unusual traffic', 'page not found', 'sorry, this page'
    )
    blocked = any(marker in combined.lower() for marker in blocked_markers)
    useful = bool((og_title or title) and (desc or jsonld or len(visible) > 120))
    quality = 'good' if useful and not blocked else (
        'limited' if (title or desc or jsonld or len(visible) > 80) else 'unavailable'
    )
    return {
        'ok': status >= 200 and status < 400,
        'status': status,
        'url': canonical_url or final_url,
        'title': (og_title or title)[:220],
        'description': desc[:1000],
        'jsonld': jsonld[:2500],
        'text': visible[:8000],
        'quality': quality,
    }

def fetch_public(url):
    # Direct fetch first; if a social site returns a login/challenge shell,
    # read the exact same supplied URL through Jina Reader.
    url = normalize_url(url)
    host = source_host(url)
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; PairwisePublicMetadata/1.0)',
        'Accept': 'text/html,application/xhtml+xml,text/plain;q=0.9'
    }

    try:
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        content_type = r.headers.get('content-type', '').lower()
        if r.ok and ('html' in content_type or r.text):
            parsed = _parse_html(r.text, r.url, r.status_code)
            parsed['host'] = host
            if parsed['quality'] == 'good':
                parsed['method'] = 'direct'
                parsed['reason'] = ''
                return parsed
            direct = parsed
        else:
            direct = {
                'ok': False, 'status': r.status_code, 'url': r.url,
                'title': '', 'description': '', 'jsonld': '', 'text': '',
                'quality': 'unavailable', 'host': host,
                'method': 'direct', 'reason': 'Source did not return useful HTML.'
            }
    except requests.RequestException as e:
        direct = {
            'ok': False, 'status': 0, 'url': url, 'title': '', 'description': '',
            'jsonld': '', 'text': '', 'quality': 'unavailable', 'host': host,
            'method': 'direct', 'reason': f'Direct fetch failed: {type(e).__name__}.'
        }

    try:
        reader_url = 'https://r.jina.ai/' + url
        rr = requests.get(
            reader_url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; PairwiseReader/1.0)'},
            timeout=15
        )
        if rr.ok and rr.text.strip():
            text = re.sub(r'\s+', ' ', rr.text).strip()
            title = ''
            for line in rr.text.splitlines():
                line = line.strip().lstrip('#').strip()
                if line:
                    title = line[:220]
                    break
            quality = 'good' if len(text) >= 120 else 'limited'
            return {
                'ok': True, 'status': rr.status_code, 'url': url, 'host': host,
                'title': title, 'description': text[:1000],
                'jsonld': '', 'text': text[:8000],
                'quality': quality, 'method': 'reader',
                'reason': '' if quality == 'good' else 'Only limited public metadata was available.'
            }
    except requests.RequestException:
        pass

    direct['reason'] = 'Only limited public metadata was available; no unsupported traits were invented.'
    return direct

def extract_signals(text):
    text = re.sub(r'\s+', ' ', text or '').lower()
    groups = {
        'technology': ['technology', 'software', 'engineering', 'developer', 'saas', 'product'],
        'ai': ['artificial intelligence', 'machine learning', 'generative ai', ' ai ', 'llm'],
        'startup': ['startup', 'founder', 'entrepreneur', 'venture', 'business'],
        'design': ['design', 'designer', 'creative', 'ux', 'ui'],
        'music': ['music', 'song', 'singing', 'guitar', 'piano', 'dj'],
        'fitness': ['fitness', 'gym', 'running', 'workout', 'health'],
        'travel': ['travel', 'travelling', 'traveling', 'adventure', 'explore'],
        'finance': ['finance', 'investing', 'investment', 'fintech', 'markets'],
        'writing': ['writing', 'writer', 'blog', 'author', 'content'],
        'education': ['education', 'teaching', 'teacher', 'learning', 'student'],
        'marketing': ['marketing', 'branding', 'brand', 'advertising', 'influencer'],
        'photography': ['photography', 'photographer', 'camera'],
        'food': ['food', 'cooking', 'chef', 'restaurant'],
        'sports': ['football', 'cricket', 'basketball', 'tennis', 'sports'],
    }
    found = []
    for key, terms in groups.items():
        if any(term in text for term in terms):
            found.append(key)
    return found[:6]

def new_profile(linkedin, instagram):
    linkedin = normalize_url(linkedin)
    instagram = normalize_url(instagram)
    ln = fetch_public(linkedin)
    ig = fetch_public(instagram)

    ln_text = ' '.join([ln.get('title', ''), ln.get('description', ''), ln.get('jsonld', ''), ln.get('text', '')])
    ig_text = ' '.join([ig.get('title', ''), ig.get('description', ''), ig.get('jsonld', ''), ig.get('text', '')])
    combined = f'{ln_text} {ig_text}'
    interests = extract_signals(combined)

    name = ''
    title = ln.get('title', '')
    if title:
        clean_title = re.sub(r'\s+', ' ', title)
        m = re.match(r'^([^|–-]{2,80})\s*[|–-]', clean_title)
        if m:
            name = m.group(1).strip()
        elif 'LinkedIn' not in clean_title and 'Instagram' not in clean_title:
            name = clean_title[:80].strip()
    if not name:
        name = slug_name(linkedin) or slug_name(instagram) or 'New profile'

    role = 'Analyzed from supplied public-source metadata'
    if ln.get('description'):
        role = ln['description'][:180]

    source_quality = {
        'LinkedIn': ln.get('quality', 'unavailable'),
        'Instagram': ig.get('quality', 'unavailable')
    }

    topics = interests[:6]
    return {
        'id': 'custom',
        'name': name,
        'role': role,
        'linkedin': linkedin,
        'instagram': instagram,
        'interests': topics,
        'hobbies': topics[:3],
        'style': 'Evidence-based profile read' if topics else 'Evidence-limited',
        'values': topics[:3],
        'live': True,
        'linkedin_snapshot': ln,
        'instagram_snapshot': ig,
        'source_quality': source_quality,
        'usable_sources': sum(v == 'good' for v in source_quality.values()),
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
    if not linkedin or not instagram:
        return JSONResponse({'error': 'Both public URLs are required.'}, status_code=400)
    linkedin = normalize_url(linkedin)
    instagram = normalize_url(instagram)
    if source_host(linkedin) not in {'linkedin.com', 'in.linkedin.com'}:
        return JSONResponse({'error': 'Please provide a public LinkedIn profile URL.'}, status_code=400)
    if source_host(instagram) not in {'instagram.com'}:
        return JSONResponse({'error': 'Please provide a public Instagram profile URL.'}, status_code=400)
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
