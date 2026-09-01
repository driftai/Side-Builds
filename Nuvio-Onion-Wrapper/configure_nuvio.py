from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json

ROOT = Path(__file__).resolve().parent
p = ROOT / 'nuvio-wrapper.properties'
old = {}
if p.exists():
    for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            old[k.strip()] = v.strip()


def discover_backend(url):
    base = (url or '').strip().rstrip('/')
    if not base:
        return {}
    try:
        req = Request(base + '/.well-known/nuvio', headers={'User-Agent': 'Nuvio-Onion-Wrapper/7.0', 'Accept': 'application/json'})
        with urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode('utf-8', 'replace'))
            return data if isinstance(data, dict) else {}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return {}


def ask(key, prompt, default=''):
    d = old.get(key, default)
    shown = f' [{d}]' if d else ''
    v = input(prompt + shown + ': ').strip()
    return v or d


print('Nuvio Wrapper - account/trailer configuration')
print('The public Nuvio key is client configuration. Never enter a service-role secret.')
vals = {}
vals['NUVIO_SUPABASE_URL'] = ask('NUVIO_SUPABASE_URL', 'Backend URL', 'https://api.nuvio.tv')

existing_key = old.get('NUVIO_SUPABASE_ANON_KEY', '').strip()
if not existing_key:
    discovery = discover_backend(vals['NUVIO_SUPABASE_URL'])
    existing_key = str(discovery.get('publishable_key') or '').strip()
    if existing_key:
        print('Discovered Nuvio public key automatically from the backend.')

if existing_key:
    print('Nuvio publishable/anon key: using discovered/saved public client key.')
    vals['NUVIO_SUPABASE_ANON_KEY'] = existing_key
else:
    vals['NUVIO_SUPABASE_ANON_KEY'] = ask('NUVIO_SUPABASE_ANON_KEY', 'Nuvio publishable/anon key')

vals['TV_LOGIN_WEB_BASE_URL'] = ask('TV_LOGIN_WEB_BASE_URL', 'TV login web base URL', 'https://nuvio.tv/tv-login')
vals['YOUTUBE_PROXY_URL'] = ask('YOUTUBE_PROXY_URL', 'YouTube proxy path', 'youtube-proxy.html')
vals['AVATAR_PUBLIC_BASE_URL'] = ask('AVATAR_PUBLIC_BASE_URL', 'Avatar base URL', '')
p.write_text('\n'.join(f'{k}={v}' for k, v in vals.items()) + '\n', encoding='utf-8')
print('\nSaved:', p)
if not vals['NUVIO_SUPABASE_ANON_KEY']:
    print('WARNING: public key still missing; QR sign-in will remain disabled.')
else:
    print('QR account configuration is present.')
print('Run START_WRAPPER.bat again.')
