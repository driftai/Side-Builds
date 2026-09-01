from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, urlopen, HTTPRedirectHandler, HTTPSHandler, build_opener
from urllib.error import URLError, HTTPError
import argparse
import ipaddress
import json
import mimetypes
import os
import re
import socket
import ssl
import sys
import time

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
REQUIRED = ('index.html', 'app.bundle.js', 'core-js.bundle.js', 'nuvio.env.js')
_DISCOVERY_CACHE = {'at': 0, 'data': {}}
_DISCOVERY_TTL = 300
PRIVATE_HOSTS = {'localhost', 'localhost.localdomain', 'ip6-localhost', 'ip6-loopback'}
ADDON_API_PATH_RE = re.compile(r'(?:^|/)(?:manifest\.json|catalog/|meta/|stream/|subtitles/)', re.I)
MAX_PROXY_BODY = 2 * 1024 * 1024
SSL_CONTEXT = ssl.create_default_context()
PUBLIC_ENV_KEYS = (
    'NUVIO_SUPABASE_URL', 'NUVIO_SUPABASE_ANON_KEY', 'TV_LOGIN_WEB_BASE_URL',
    'YOUTUBE_PROXY_URL', 'INTRODB_API_URL', 'AVATAR_PUBLIC_BASE_URL',
    'UNIQUE_CONTRIBUTIONS_BASE_URL', 'SUPPORTERS_API_BASE_URL', 'SUPPORT_URL',
    'SPONSOR_NAMES', 'SIMKL_APP_NAME',
)


def built_ok(dist: Path) -> bool:
    return dist.is_dir() and all((dist / name).is_file() for name in REQUIRED)


def safe_child(root: Path, rel: str):
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def parse_props(path: Path):
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('!') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        out[k.strip()] = v.strip()
    return out


def read_wrapper_config():
    return parse_props(ROOT / 'nuvio-wrapper.properties')


def find_nonempty_env(dist: Path):
    p = dist / 'nuvio.env.js'
    if not p.is_file():
        return {}
    txt = p.read_text(encoding='utf-8', errors='replace')
    out = {}
    keys = ('NUVIO_SUPABASE_URL', 'NUVIO_SUPABASE_ANON_KEY', 'TV_LOGIN_WEB_BASE_URL', 'YOUTUBE_PROXY_URL', 'AVATAR_PUBLIC_BASE_URL')
    for key in keys:
        patterns = [rf'"{re.escape(key)}"\\s*:\\s*"([^"]*)"', rf'{re.escape(key)}\\s*[:=]\\s*["\']([^"\']*)["\']']
        for pattern in patterns:
            match = re.search(pattern, txt)
            if match and match.group(1).strip():
                out[key] = match.group(1).strip()
                break
    return out


def discover_backend(backend_url: str):
    backend_url = (backend_url or '').rstrip('/')
    if not backend_url:
        return {}
    now = time.time()
    if _DISCOVERY_CACHE['data'] and now - _DISCOVERY_CACHE['at'] < _DISCOVERY_TTL:
        cached_backend = _DISCOVERY_CACHE['data'].get('backend_url', '').rstrip('/')
        if cached_backend == backend_url:
            return dict(_DISCOVERY_CACHE['data'])
    url = backend_url + '/.well-known/nuvio'
    try:
        req = Request(url, headers={'User-Agent': 'Nuvio-Onion-Wrapper/17.0', 'Accept': 'application/json'})
        with urlopen(req, timeout=8, context=SSL_CONTEXT) as response:
            payload = json.loads(response.read().decode('utf-8', 'replace'))
            if isinstance(payload, dict):
                payload['backend_url'] = payload.get('backend_url') or backend_url
                _DISCOVERY_CACHE.update(at=now, data=payload)
                return dict(payload)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        print('Nuvio discovery unavailable:', exc)
    return {}


def merged_config(dist: Path):
    cfg = read_wrapper_config()
    existing = find_nonempty_env(dist)
    merged = {**existing, **{k: v for k, v in cfg.items() if v.strip()}}
    merged.setdefault('NUVIO_SUPABASE_URL', 'https://api.nuvio.tv')
    discovery = discover_backend(merged.get('NUVIO_SUPABASE_URL', ''))
    if not merged.get('NUVIO_SUPABASE_ANON_KEY') and discovery.get('publishable_key'):
        merged['NUVIO_SUPABASE_ANON_KEY'] = str(discovery['publishable_key']).strip()
    merged.setdefault('TV_LOGIN_WEB_BASE_URL', 'https://nuvio.tv/tv-login')
    merged.setdefault('YOUTUBE_PROXY_URL', 'youtube-proxy.html')
    return merged, discovery


def runtime_env_script(dist: Path):
    merged, _ = merged_config(dist)
    vals = {key: merged.get(key, '') for key in PUBLIC_ENV_KEYS}
    vals['YOUTUBE_PROXY_URL'] = '/__wrapper__/youtube-proxy.html'
    env_json = json.dumps(vals, separators=(',', ':'))
    bootstrap = r'''(function(){
  var r=typeof globalThis!=="undefined"?globalThis:window;
  r.__NUVIO_ENV__=%s;
  (function(){
    var nativeFetch=r.fetch && r.fetch.bind(r);
    function rewrite(input){
      var raw=typeof input==="string"?input:(input&&input.url?input.url:"");
      try{
        var u=new URL(raw,location.href);
        var host=(u.hostname||"").toLowerCase();
        var isLocal=host==="127.0.0.1"||host==="localhost"||host===location.hostname;
        if(!isLocal && (u.protocol==="https:" || u.protocol==="http:")){
          var path=u.pathname||"";
          if(/(?:^|\/)(?:manifest\.json|catalog\/|meta\/|stream\/|subtitles\/)/i.test(path)){
            return "/__wrapper__/addon-proxy?url="+encodeURIComponent(u.href);
          }
        }
      }catch(_){}
      return raw;
    }
    r.__NUVIO_BROWSER_WRAPPER__=true;
    try{
      var rawSetItem=localStorage.setItem.bind(localStorage);
      if(!r.__nuvioWrapperStoragePatched){
        var forceNoTrailerAutoplay=function(value){
          try{
            var parsed=JSON.parse(String(value));
            if(parsed && parsed.__profileScoped===true && parsed.profiles && typeof parsed.profiles==="object"){
              Object.keys(parsed.profiles).forEach(function(id){
                if(parsed.profiles[id] && typeof parsed.profiles[id]==="object") parsed.profiles[id].trailerAutoplay=false;
              });
            }else if(parsed && typeof parsed==="object"){ parsed.trailerAutoplay=false; }
            return JSON.stringify(parsed);
          }catch(_){ return value; }
        };
        localStorage.setItem=function(key,value){
          if(String(key||"")==="playerSettings") value=forceNoTrailerAutoplay(value);
          return rawSetItem(String(key),value);
        };
        try{
          var currentSettings=localStorage.getItem("playerSettings");
          if(currentSettings!=null) rawSetItem("playerSettings",forceNoTrailerAutoplay(currentSettings));
        }catch(_){}
        r.__nuvioWrapperStoragePatched=true;
      }
    }catch(_){}
    if(nativeFetch && !r.__nuvioWrapperFetchPatched){
      r.fetch=function(input,init){
        var rewritten=rewrite(input);
        if(typeof input==="string") return nativeFetch(rewritten,init);
        try{return nativeFetch(new Request(rewritten,input),init);}catch(_){return nativeFetch(rewritten,init);}
      };
      r.__nuvioWrapperFetchPatched=true;
    }
  }());
}());
''' % env_json
    return bootstrap


def trailer_proxy_html(dist: Path):
    src = dist / 'youtube-proxy.html'
    if not src.is_file():
        return None
    html = src.read_text(encoding='utf-8', errors='replace')
    html = html.replace('var pageOrigin = String((location && location.origin) || "").trim();', 'var pageOrigin = "https://nuvio.tv";')
    html = html.replace('var widgetReferrer = pageOriginIsHttp ? location.href : "https://www.youtube.com";', 'var widgetReferrer = "https://nuvio.tv/";')
    html = html.replace('var autoplay = params.autoplay !== "0";', 'var autoplay = false;')
    html = html.replace('                 if (autoplay) {\n                   event.target.playVideo();\n                 }\n', '')
    html = html.replace('}, 4500);', '}, 2500);')
    return html


def _resolved_addresses(host: str):
    addresses = set()
    try:
        for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
            sockaddr = result[4]
            if sockaddr:
                addresses.add(sockaddr[0])
    except socket.gaierror:
        return set()
    return addresses


def is_public_target(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower().rstrip('.')
        if parsed.scheme != 'https' or not host or host in PRIVATE_HOSTS:
            return False
        try:
            ip = ipaddress.ip_address(host)
            return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast)
        except ValueError:
            pass
        addresses = _resolved_addresses(host)
        if not addresses:
            return False
        return all(not (ipaddress.ip_address(addr).is_private or ipaddress.ip_address(addr).is_loopback or ipaddress.ip_address(addr).is_link_local or ipaddress.ip_address(addr).is_reserved or ipaddress.ip_address(addr).is_multicast) for addr in addresses)
    except Exception:
        return False


def is_allowed_addon_api_target(url: str) -> bool:
    if not is_public_target(url):
        return False
    try:
        return bool(ADDON_API_PATH_RE.search(urlsplit(url).path or ''))
    except Exception:
        return False


class SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not is_public_target(newurl):
            raise HTTPError(req.full_url, 403, 'Redirect target is not allowed', headers, None)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _safe_opener():
    return build_opener(HTTPSHandler(context=SSL_CONTEXT), SafeRedirectHandler)


def _public_forward_headers(handler):
    headers = {key: value for key, value in handler.headers.items() if key.lower() in {'accept', 'content-type'}}
    headers['User-Agent'] = 'Nuvio-Onion-Wrapper/17.0'
    headers.setdefault('Accept', 'application/json, text/plain, */*')
    headers['Accept-Encoding'] = 'identity'
    return headers


def _proxy_addon(handler, target_url: str, method='GET', body=None):
    if not is_allowed_addon_api_target(target_url):
        handler.send_error(403, 'Addon API proxy target is not allowed')
        return
    if body is not None and len(body) > MAX_PROXY_BODY:
        handler.send_error(413, 'Request body is too large')
        return
    try:
        req = Request(target_url, data=body, headers=_public_forward_headers(handler), method=method)
        with _safe_opener().open(req, timeout=60) as response:
            payload = response.read(MAX_PROXY_BODY + 1)
            if len(payload) > MAX_PROXY_BODY:
                handler.send_error(502, 'Remote response is too large')
                return
            handler.send_response(getattr(response, 'status', 200))
            handler.send_header('Content-Type', response.headers.get('Content-Type') or 'application/json; charset=utf-8')
            handler.send_header('Content-Length', str(len(payload)))
            handler.send_header('Cache-Control', 'no-store')
            handler.send_header('Access-Control-Allow-Origin', '*')
            handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
            handler.end_headers()
            handler.wfile.write(payload)
    except HTTPError as exc:
        payload = exc.read(MAX_PROXY_BODY)
        handler.send_response(exc.code)
        handler.send_header('Content-Type', exc.headers.get('Content-Type') if exc.headers else 'text/plain; charset=utf-8')
        handler.send_header('Content-Length', str(len(payload)))
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.end_headers()
        handler.wfile.write(payload)
    except Exception as exc:
        handler.send_error(502, 'Addon API proxy failed: %s' % exc)


parser = argparse.ArgumentParser()
parser.add_argument('--nuvio-root', default=os.environ.get('NUVIO_PATH') or str(ROOT / 'nuvio'))
parser.add_argument('--port', type=int, default=8797)
parser.add_argument('--check-only', action='store_true')
args = parser.parse_args()
nuvio_root = Path(args.nuvio_root).expanduser().resolve()
NUVIO_DIST = nuvio_root / 'dist'


class Handler(SimpleHTTPRequestHandler):
    SAFE_ROOT_FILES = {
        '/': ROOT / 'index.html',
        '/index.html': ROOT / 'index.html',
        '/wrapper/assets/wrapper.css': ROOT / 'wrapper' / 'assets' / 'wrapper.css',
        '/wrapper/assets/wrapper.js': ROOT / 'wrapper' / 'assets' / 'wrapper.js',
    }

    def _serve_file(self, path: Path, ctype=None):
        if not path.is_file():
            self.send_error(404, 'File not found')
            return
        data = path.read_bytes()
        ctype = ctype or mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _serve_bytes(self, data, ctype):
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        path = urlsplit(self.path).path
        if path == '/__wrapper__/addon-proxy':
            self.send_response(204)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Accept')
            self.end_headers()
            return
        self.send_response(204)
        self.end_headers()

    def do_POST(self):
        parsed = urlsplit(self.path)
        if parsed.path != '/__wrapper__/addon-proxy':
            self.send_error(405, 'Method not allowed')
            return
        target = parse_qs(parsed.query).get('url', [''])[0]
        if not target:
            self.send_error(400, 'Missing url')
            return
        try:
            content_length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            content_length = 0
        if content_length < 0 or content_length > MAX_PROXY_BODY:
            self.send_error(413, 'Request body is too large')
            return
        body = self.rfile.read(content_length) if content_length else None
        _proxy_addon(self, target, method='POST', body=body)

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if path == '/__wrapper__/addon-proxy':
            target = parse_qs(parsed.query).get('url', [''])[0]
            if not target:
                self.send_error(400, 'Missing url')
                return
            _proxy_addon(self, target, method='GET')
            return
        if path == '/__wrapper__/nuvio-entry':
            ok = built_ok(NUVIO_DIST)
            merged, discovery = merged_config(NUVIO_DIST)
            payload = {'path': '/nuvio/index.html' if ok else None, 'built': ok, 'qrConfigured': bool(merged.get('NUVIO_SUPABASE_URL') and merged.get('NUVIO_SUPABASE_ANON_KEY')), 'backend': merged.get('NUVIO_SUPABASE_URL', 'https://api.nuvio.tv'), 'tvLogin': merged.get('TV_LOGIN_WEB_BASE_URL', 'https://nuvio.tv/tv-login'), 'discovery': bool(discovery.get('publishable_key'))}
            self._serve_bytes(json.dumps(payload).encode(), 'application/json; charset=utf-8')
            return
        if path == '/__wrapper__/nuvio-env.js':
            self._serve_bytes(runtime_env_script(NUVIO_DIST).encode(), 'application/javascript; charset=utf-8')
            return
        if path == '/__wrapper__/diagnostics':
            merged, discovery = merged_config(NUVIO_DIST)
            payload = {'built': built_ok(NUVIO_DIST), 'backend': merged.get('NUVIO_SUPABASE_URL', ''), 'qrConfigured': bool(merged.get('NUVIO_SUPABASE_URL') and merged.get('NUVIO_SUPABASE_ANON_KEY')), 'keySource': 'wrapper-properties' if read_wrapper_config().get('NUVIO_SUPABASE_ANON_KEY') else ('discovery' if discovery.get('publishable_key') else ('built-env' if find_nonempty_env(NUVIO_DIST).get('NUVIO_SUPABASE_ANON_KEY') else 'missing')), 'tvLogin': merged.get('TV_LOGIN_WEB_BASE_URL', '')}
            self._serve_bytes(json.dumps(payload, indent=2).encode(), 'application/json; charset=utf-8')
            return
        if path == '/__wrapper__/youtube-proxy.html':
            if not built_ok(NUVIO_DIST):
                self.send_error(404, 'Nuvio browser build is missing')
                return
            html = trailer_proxy_html(NUVIO_DIST)
            if html is None:
                self.send_error(404, 'Nuvio YouTube proxy is missing')
                return
            self._serve_bytes(html.encode('utf-8'), 'text/html; charset=utf-8')
            return
        if path in self.SAFE_ROOT_FILES:
            self._serve_file(self.SAFE_ROOT_FILES[path])
            return
        if path in ('/nuvio', '/nuvio/'):
            if not built_ok(NUVIO_DIST):
                self.send_error(404, 'Nuvio browser build is missing')
                return
            self._serve_file(NUVIO_DIST / 'index.html')
            return
        if path == '/nuvio/nuvio.env.js':
            if not built_ok(NUVIO_DIST):
                self.send_error(404, 'Nuvio browser build is missing')
                return
            self._serve_bytes(runtime_env_script(NUVIO_DIST).encode(), 'application/javascript; charset=utf-8')
            return
        if path.startswith('/nuvio/'):
            if not built_ok(NUVIO_DIST):
                self.send_error(404, 'Nuvio browser build is missing')
                return
            rel = path[len('/nuvio/'):]
            candidate = safe_child(NUVIO_DIST, rel)
            if candidate is None:
                self.send_error(403, 'Forbidden')
                return
            self._serve_file(candidate)
            return
        self.send_error(404, 'Not found')

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'SAMEORIGIN')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Permissions-Policy', 'autoplay=*, encrypted-media=*, fullscreen=*, picture-in-picture=*, web-share=*')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stdout.write('%s - %s\n' % (self.address_string(), fmt % args))
        sys.stdout.flush()


def main():
    if args.check_only:
        ok = built_ok(NUVIO_DIST)
        print('FOUND' if ok else 'NOT FOUND')
        return 0 if ok else 1
    merged, discovery = merged_config(NUVIO_DIST)
    print('Nuvio Wrapper running at http://127.0.0.1:%d/' % args.port)
    print('Nuvio inner app: ' + (str(NUVIO_DIST / 'index.html') if built_ok(NUVIO_DIST) else 'NOT BUILT'))
    print('QR config: ' + ('READY' if merged.get('NUVIO_SUPABASE_URL') and merged.get('NUVIO_SUPABASE_ANON_KEY') else 'MISSING PUBLIC KEY'))
    print('Discovery key: ' + ('AVAILABLE' if discovery.get('publishable_key') else 'NOT AVAILABLE'))
    print('Remote addon proxy: HTTPS-only, DNS-public-only, allow-listed API paths')
    print('Filesystem surface: wrapper entry + wrapper assets + /nuvio/dist only')
    print('Nuvio source location is user-selected and never committed by the wrapper.')
    print('Press Ctrl+C in this window to stop the local server.')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
