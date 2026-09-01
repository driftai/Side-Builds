import json, os, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
checks=[]

def ok(name, detail=''):
    checks.append((True,name,detail))
    print(f'[PASS] {name}' + (f' — {detail}' if detail else ''))

def fail(name, detail=''):
    checks.append((False,name,detail))
    print(f'[FAIL] {name}' + (f' — {detail}' if detail else ''))

# Locate Nuvio the same way as the launcher.
paths=[]
env=os.environ.get('NUVIO_PATH','').strip()
if env: paths.append(Path(env))
paths += [ROOT/'nuvio', ROOT.parent/'nuvio']
nuvio=None
for p in paths:
    if (p/'package.json').is_file():
        nuvio=p.resolve(); break
if not nuvio:
    fail('Nuvio source location', 'Expected .\\nuvio, ..\\nuvio, or NUVIO_PATH')
else:
    ok('Nuvio source location', str(nuvio))
    dist=nuvio/'dist'
    required=['index.html','app.bundle.js','core-js.bundle.js','nuvio.env.js']
    missing=[x for x in required if not (dist/x).is_file()]
    if missing: fail('Nuvio browser build', 'Missing: '+', '.join(missing))
    else: ok('Nuvio browser build', str(dist))

base='http://127.0.0.1:8797'
_spawned_server = None
try:
    urllib.request.urlopen(base + '/__wrapper__/nuvio-entry', timeout=1)
except Exception:
    import threading, time, server as srv_module
    if nuvio:
        srv_module.nuvio_root = nuvio
        srv_module.NUVIO_DIST = nuvio / 'dist'
    _spawned_server = srv_module.ThreadingHTTPServer(('127.0.0.1', 8797), srv_module.Handler)
    _server_thread = threading.Thread(target=_spawned_server.serve_forever, daemon=True)
    _server_thread.start()
    time.sleep(0.5)

def get(path):
    req=urllib.request.Request(base+path,headers={'Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=5) as r:
        return r.status, r.headers.get('content-type',''), r.read()

def expect_http_error(path, expected_code):
    try:
        get(path)
        fail(path, f'Expected HTTP {expected_code}')
    except urllib.error.HTTPError as e:
        if e.code == expected_code:
            ok(path, f'HTTP {e.code}')
        else:
            fail(path, f'Expected HTTP {expected_code}, got {e.code}')
    except Exception as e:
        fail(path, repr(e))

try:
    status,ctype,body=get('/')
    ok('Wrapper HTTP root', f'{status} {ctype}')
except Exception as e:
    fail('Wrapper HTTP root', repr(e))

for path in ['/wrapper/assets/wrapper.js', '/__wrapper__/nuvio-entry', '/__wrapper__/nuvio-env.js']:
    try:
        status,ctype,body=get(path)
        if status==200: ok(path, f'{status} {ctype}')
        else: fail(path, f'HTTP {status}')
    except Exception as e:
        fail(path, repr(e))

try:
    status,ctype,body=get('/__wrapper__/diagnostics')
    payload=json.loads(body.decode('utf-8','replace'))
    safe_keys=('built','backend','qrConfigured','keySource','tvLogin')
    ok('Wrapper diagnostics', json.dumps({k:payload.get(k) for k in safe_keys}, separators=(',',':')))
    leaked={'nuvio_root','dist','root'} & set(payload.keys())
    if leaked:
        fail('Diagnostics filesystem redaction', f'Unexpected host path fields: {sorted(leaked)}')
    else:
        ok('Diagnostics filesystem redaction', 'No host filesystem paths exposed')
except Exception as e:
    fail('Wrapper diagnostics', repr(e))

try:
    status,ctype,body=get('/__wrapper__/nuvio-env.js')
    text=body.decode('utf-8','replace')
    forbidden=['TRAKT_CLIENT_SECRET','TMDB_API_KEY','PREMIUMIZE_CLIENT_ID','SECRET','PASSWORD']
    leaked=[x for x in forbidden if x in text]
    if leaked:
        fail('Browser runtime secret redaction', 'Sensitive config names present: '+', '.join(leaked))
    else:
        ok('Browser runtime secret redaction', 'Sensitive credential fields are not exported')
except Exception as e:
    fail('Browser runtime secret redaction', repr(e))

# The generic remote proxy was intentionally removed; only the allow-listed addon proxy remains.
expect_http_error('/__wrapper__/proxy?url=https%3A%2F%2Fexample.com%2F', 404)
expect_http_error('/__wrapper__/addon-proxy?url=https%3A%2F%2F127.0.0.1%2Fmanifest.json', 403)
expect_http_error('/__wrapper__/addon-proxy?url=http%3A%2F%2Fexample.com%2Fmanifest.json', 403)
expect_http_error('/__wrapper__/addon-proxy?url=https%3A%2F%2Fexample.com%2Fprivate%2Fsecret.json', 403)

# Test wrapper compatibility CSS ensures trailer layers do not occlude action buttons
try:
    wrapper_js = (ROOT / 'wrapper' / 'assets' / 'wrapper.js').read_text(encoding='utf-8', errors='replace')
    if '.detail-trailer-layer' in wrapper_js and 'pointer-events: none !important' in wrapper_js and 'z-index: 10 !important' in wrapper_js:
        ok('Detail button non-occlusion CSS', 'Trailer layer inert, content elevated to z-index 10')
    else:
        fail('Detail button non-occlusion CSS', 'Trailer layer might occlude detail actions')
except Exception as e:
    fail('Detail button non-occlusion CSS', repr(e))

# Test built CSS contains cursor pointer rules for interactive focusables
try:
    css_files = list((nuvio / 'dist' / 'css').glob('*.css')) if nuvio else []
    has_cursor_pointer = any('cursor:pointer' in f.read_text(encoding='utf-8', errors='replace').replace(' ', '') for f in css_files)
    if has_cursor_pointer:
        ok('Cursor pointer interactive styling', f'Present across {len(css_files)} CSS bundles')
    else:
        fail('Cursor pointer interactive styling', 'Missing cursor:pointer in dist CSS')
except Exception as e:
    fail('Cursor pointer interactive styling', repr(e))

# Test addon-proxy validation endpoint with a sample public Stremio manifest and meta endpoint
try:
    test_addon_url = 'https://v3-cinemeta.strem.io/manifest.json'
    status,ctype,body=get('/__wrapper__/addon-proxy?url='+urllib.request.quote(test_addon_url))
    manifest=json.loads(body.decode('utf-8','replace'))
    if manifest.get('id'):
        ok('Addon proxy test', f"{manifest.get('id')} ({status})")
    else:
        fail('Addon proxy test', f"Unexpected payload: {body[:60]}")
except Exception as e:
    fail('Addon proxy test', repr(e))

# Test movie Cinemeta metadata resolution (translates IMDb to TMDB without requiring API key)
try:
    test_movie_url = 'https://v3-cinemeta.strem.io/meta/movie/tt0111161.json'
    status,ctype,body=get('/__wrapper__/addon-proxy?url='+urllib.request.quote(test_movie_url))
    meta_payload=json.loads(body.decode('utf-8','replace'))
    moviedb_id = meta_payload.get('meta', {}).get('moviedb_id')
    if moviedb_id == 278:
        ok('Movie metadata & TMDB resolution', f"tt0111161 -> TMDB {moviedb_id}")
    else:
        fail('Movie metadata & TMDB resolution', f"Unexpected TMDB ID: {moviedb_id}")
except Exception as e:
    fail('Movie metadata & TMDB resolution', repr(e))

if _spawned_server:
    _spawned_server.shutdown()
    _spawned_server.server_close()

failed=sum(1 for x,_,_ in checks if not x)
print(f'\nSmoke result: {len(checks)-failed} passed, {failed} failed')
sys.exit(1 if failed else 0)
