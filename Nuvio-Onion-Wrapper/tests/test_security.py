import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import server


def test_private_targets_rejected():
    assert not server.is_public_target('http://127.0.0.1:8000/x')
    assert not server.is_public_target('https://127.0.0.1:8000/x')
    assert not server.is_public_target('https://localhost/x')
    assert not server.is_public_target('https://192.168.1.10/x')
    assert not server.is_public_target('https://10.0.0.5/x')
    assert not server.is_public_target('https://172.16.0.5/x')
    assert not server.is_public_target('ftp://example.com/x')


def test_public_target_validation_is_dns_aware():
    original = server._resolved_addresses
    try:
        server._resolved_addresses = lambda host: {'93.184.216.34'}
        assert server.is_public_target('https://example.com/path')
        server._resolved_addresses = lambda host: {'10.0.0.5'}
        assert not server.is_public_target('https://evil.example/path')
    finally:
        server._resolved_addresses = original


def test_addon_target_requires_https_and_expected_path():
    original = server._resolved_addresses
    try:
        server._resolved_addresses = lambda host: {'93.184.216.34'}
        assert server.is_allowed_addon_api_target('https://addon.example/manifest.json')
        assert server.is_allowed_addon_api_target('https://addon.example/catalog/movie/top.json')
        assert not server.is_allowed_addon_api_target('http://addon.example/manifest.json')
        assert not server.is_allowed_addon_api_target('https://addon.example/private/config.json')
    finally:
        server._resolved_addresses = original


def test_runtime_env_contains_no_sensitive_credentials(tmp_path: Path):
    dist = tmp_path / 'dist'
    dist.mkdir()
    (dist / 'nuvio.env.js').write_text(
        'TRAKT_CLIENT_SECRET="super-secret"\n'
        'TMDB_API_KEY="api-secret"\n'
        'NUVIO_SUPABASE_ANON_KEY="public-key"\n',
        encoding='utf-8',
    )
    original_root = server.ROOT
    original_discover = server.discover_backend
    try:
        server.ROOT = tmp_path
        server.discover_backend = lambda _url: {}
        (tmp_path / 'nuvio-wrapper.properties').write_text(
            'NUVIO_SUPABASE_URL=https://api.nuvio.tv\n'
            'NUVIO_SUPABASE_ANON_KEY=public-key\n'
            'TRAKT_CLIENT_SECRET=local-secret\n'
            'TMDB_API_KEY=local-api-key\n',
            encoding='utf-8',
        )
        script = server.runtime_env_script(dist)
        assert 'super-secret' not in script
        assert 'api-secret' not in script
        assert 'local-secret' not in script
        assert 'local-api-key' not in script
        payload_text = script.split('__NUVIO_ENV__=', 1)[1].split(';', 1)[0]
        payload = json.loads(payload_text)
        assert 'TRAKT_CLIENT_SECRET' not in payload
        assert 'TMDB_API_KEY' not in payload
        assert payload['NUVIO_SUPABASE_ANON_KEY'] == 'public-key'
    finally:
        server.ROOT = original_root
        server.discover_backend = original_discover


def test_filesystem_surface_is_allow_listed():
    allowed = server.Handler.SAFE_ROOT_FILES
    assert '/' in allowed
    assert '/index.html' in allowed
    assert '/wrapper/assets/wrapper.js' in allowed
    assert '/wrapper/assets/wrapper.css' in allowed
    assert '/server.py' not in allowed
    assert '/configure_nuvio.py' not in allowed
    assert '/AGY_AGENT_REPORT.md' not in allowed


def test_safe_child_path_traversal_prevention(tmp_path: Path):
    root = tmp_path / "nuvio_dist"
    root.mkdir()
    (root / "index.html").write_text("ok", encoding="utf-8")
    
    # Valid child
    assert server.safe_child(root, "index.html") == (root / "index.html").resolve()
    
    # Traversal attempts
    assert server.safe_child(root, "../secret.txt") is None
    assert server.safe_child(root, "../../Windows/System32/calc.exe") is None
    assert server.safe_child(root, "..\\..\\etc\\passwd") is None
    assert server.safe_child(root, "/etc/passwd") is None


def test_wrapper_relative_default_nuvio_path():
    default_path = server.ROOT / "nuvio"
    assert default_path.is_relative_to(server.ROOT)
    assert not str(default_path).startswith("C:\\Users\\alvin\\Downloads\\Private-Test-Builds\\nuvio")
    assert default_path.name == "nuvio"


def test_empty_and_incomplete_nuvio_validation(tmp_path: Path):
    empty_dist = tmp_path / "empty_dist"
    empty_dist.mkdir()
    assert not server.built_ok(empty_dist)

    # Incomplete dist (missing core-js.bundle.js and nuvio.env.js)
    incomplete_dist = tmp_path / "incomplete_dist"
    incomplete_dist.mkdir()
    (incomplete_dist / "index.html").write_text("html", encoding="utf-8")
    (incomplete_dist / "app.bundle.js").write_text("js", encoding="utf-8")
    assert not server.built_ok(incomplete_dist)

    # Complete dist with all 4 required files
    complete_dist = tmp_path / "complete_dist"
    complete_dist.mkdir()
    for name in server.REQUIRED:
        (complete_dist / name).write_text("ok", encoding="utf-8")
    assert server.built_ok(complete_dist)


def test_git_placeholder_separation():
    nuvio_dir = server.ROOT / "nuvio"
    assert nuvio_dir.is_dir()
    assert (nuvio_dir / ".gitkeep").is_file()


def test_arbitrary_proxy_and_tls_downgrade_are_removed():
    source = Path(server.__file__).read_text(encoding='utf-8')
    assert '/__wrapper__/proxy' not in source
    assert '_UNVERIFIED_SSL_CONTEXT' not in source
    assert 'context=_UNVERIFIED_SSL_CONTEXT' not in source
    assert 'super().do_GET()' not in source


if __name__ == '__main__':
    import pytest
    raise SystemExit(pytest.main([__file__, '-q']))
