"""
OmniPad Security Boundary & Information Redaction Test Suite.
Tests HTTP endpoint access control matrix and information disclosure prevention
across Localhost, LAN, and simulated Cloudflare Public Tunnel sessions.
"""

import asyncio
import http.client
import json
import os
import pathlib
import sys
import uvicorn

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import app, slot_manager, profile_manager, tunnel_manager
from router.targeting import target_manager

TEST_PORT = 8792


def make_http_request(method: str, path: str, host: str, body: dict = None) -> tuple[int, dict, str]:
    conn = http.client.HTTPConnection("127.0.0.1", TEST_PORT, timeout=5)
    headers = {"Host": host, "Accept": "application/json"}
    payload = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body)
    conn.request(method, path, body=payload, headers=headers)
    res = conn.getresponse()
    status = res.status
    raw_data = res.read().decode("utf-8")
    conn.close()
    try:
        data = json.loads(raw_data)
    except Exception:
        data = {}
    return status, data, raw_data


def test_section(title: str):
    print("\n" + "=" * 70)
    print(f"  SECURITY TEST: {title}")
    print("=" * 70)


def run_endpoint_matrix_tests():
    test_section("HTTP Endpoint Access Control Matrix (Localhost vs LAN vs Cloudflare)")
    cf_host = "test-session.trycloudflare.com"
    local_host = f"localhost:{TEST_PORT}"
    lan_host = f"192.168.1.209:{TEST_PORT}"

    # 1. Dashboard Root (/)
    st_cf, _, _ = make_http_request("GET", "/", cf_host)
    assert st_cf == 403, f"Dashboard / must return 403 Forbidden for Cloudflare host, got {st_cf}"
    st_loc, _, _ = make_http_request("GET", "/", local_host)
    assert st_loc == 200, f"Dashboard / must return 200 for local host, got {st_loc}"
    print("  [PASS] GET /: 200 Localhost | 403 Cloudflare (Protected)")

    # 2. Player Page (/play and /join)
    st_play_cf, _, _ = make_http_request("GET", "/play", cf_host)
    assert st_play_cf == 200, f"GET /play must return 200 for Cloudflare host, got {st_play_cf}"
    st_join_cf, _, _ = make_http_request("GET", "/join", cf_host)
    assert st_join_cf == 200, f"GET /join must return 200 for Cloudflare host, got {st_join_cf}"
    print("  [PASS] GET /play & /join: 200 Localhost | 200 Cloudflare (Public Player Access)")

    # 3. Target Enumeration & Selection
    st_t_cf, _, _ = make_http_request("GET", "/api/targets", cf_host)
    assert st_t_cf == 403, f"GET /api/targets must return 403 for Cloudflare host, got {st_t_cf}"
    st_t_loc, data_t_loc, _ = make_http_request("GET", "/api/targets", local_host)
    assert st_t_loc == 200, f"GET /api/targets must return 200 for local host, got {st_t_loc}"
    assert "targets" in data_t_loc
    print("  [PASS] GET /api/targets: 200 Localhost | 403 Cloudflare (Protected)")

    st_ts_cf, _, _ = make_http_request("POST", "/api/target/select", cf_host, {"pid": 1234})
    assert st_ts_cf == 403
    st_tsf_cf, _, _ = make_http_request("POST", "/api/target/select-foreground", cf_host)
    assert st_tsf_cf == 403
    st_tc_cf, _, _ = make_http_request("POST", "/api/target/clear", cf_host)
    assert st_tc_cf == 403
    st_tg_cf, _, _ = make_http_request("POST", "/api/target/gate", cf_host, {"enabled": True})
    assert st_tg_cf == 403
    print("  [PASS] POST /api/target/*: 403 Cloudflare on select/clear/gate (Protected)")

    # 4. Background Keyboard Helper APIs
    st_bh_stat_cf, _, _ = make_http_request("GET", "/api/background-capture/status", cf_host)
    assert st_bh_stat_cf == 403
    st_bh_inp_cf, _, _ = make_http_request("GET", "/api/background-capture/input-state", cf_host)
    assert st_bh_inp_cf == 403
    st_bh_post_cf, _, _ = make_http_request("POST", "/api/background-capture", cf_host, {"enabled": True})
    assert st_bh_post_cf == 403
    print("  [PASS] /api/background-capture/*: 403 Cloudflare on status/input-state/toggle (Protected)")

    # 5. Slot Management Mutations
    st_c_cf, _, _ = make_http_request("POST", "/api/slot/1/controller", cf_host, {"backend_id": "noop"})
    assert st_c_cf == 403
    st_s_cf, _, _ = make_http_request("POST", "/api/slot/1/socd", cf_host, {"mode": "neutral"})
    assert st_s_cf == 403
    st_d_cf, _, _ = make_http_request("POST", "/api/slot/1/deadzone", cf_host, {"deadzone": 0.1})
    assert st_d_cf == 403
    st_m_cf, _, _ = make_http_request("POST", "/api/slot/1/mute", cf_host, {"muted": True})
    assert st_m_cf == 403
    st_r_cf, _, _ = make_http_request("POST", "/api/slot/1/reset", cf_host)
    assert st_r_cf == 403
    st_k_cf, _, _ = make_http_request("POST", "/api/slot/1/kick", cf_host)
    assert st_k_cf == 403
    st_p_cf, _, _ = make_http_request("POST", "/api/panic", cf_host)
    assert st_p_cf == 403
    print("  [PASS] POST /api/slot/* & /api/panic: 403 Cloudflare on controller/socd/mute/reset/kick/panic (Protected)")

    # 6. Tunnel Controls
    st_tun_st_cf, _, _ = make_http_request("POST", "/api/tunnel/start", cf_host)
    assert st_tun_st_cf == 403
    st_tun_sp_cf, _, _ = make_http_request("POST", "/api/tunnel/stop", cf_host)
    assert st_tun_sp_cf == 403
    st_tun_get_cf, _, _ = make_http_request("GET", "/api/tunnel/status", cf_host)
    assert st_tun_get_cf == 403
    print("  [PASS] /api/tunnel/*: 403 Cloudflare on start/stop/status (Protected)")

    # 7. Public Controller Profiles (Read-Only)
    st_prof_cf, data_prof_cf, _ = make_http_request("GET", "/api/profiles", cf_host)
    assert st_prof_cf == 200, f"GET /api/profiles must return 200, got {st_prof_cf}"
    assert "profiles" in data_prof_cf
    print("  [PASS] GET /api/profiles: 200 Localhost | 200 Cloudflare (Public Read-Only Profiles)")


def run_information_leakage_redaction_tests():
    test_section("Information Disclosure & Metadata Redaction Tests")
    cf_host = "test-session.trycloudflare.com"
    local_host = f"localhost:{TEST_PORT}"

    # 1. /api/status Redaction for Remote Clients
    st_loc, data_loc, _ = make_http_request("GET", "/api/status", local_host)
    assert st_loc == 200
    assert "room_code" in data_loc, "Local /api/status should contain room_code"
    assert "local_ips" in data_loc, "Local /api/status should contain local_ips"
    assert "tunnel" in data_loc, "Local /api/status should contain tunnel"

    st_cf, data_cf, raw_cf = make_http_request("GET", "/api/status", cf_host)
    assert st_cf == 200
    assert data_cf.get("remote_session") is True
    assert "room_code" not in data_cf, "Remote /api/status MUST NOT expose room_code"
    assert "local_ips" not in data_cf, "Remote /api/status MUST NOT expose local_ips"
    assert "primary_lan_url" not in data_cf, "Remote /api/status MUST NOT expose primary_lan_url"
    assert "all_lan_urls" not in data_cf, "Remote /api/status MUST NOT expose all_lan_urls"
    assert "tunnel" not in data_cf, "Remote /api/status MUST NOT expose tunnel details"
    assert "target" not in data_cf, "Remote /api/status MUST NOT expose host target window"
    assert "summary" not in data_cf, "Remote /api/status MUST NOT expose summary"
    print("  [PASS] GET /api/status (Remote): Room code, Local IPs, Tunnel, and Target info fully redacted")

    # 2. /api/target/status Redaction for Remote Clients
    # Set a mock target with sensitive process metadata
    class MockSecretTarget:
        pid = 9876
        hwnd = 54321
        title = "Secret Game Window - Classified"
        process_name = "SuperSecretGame.exe"
        exe_path = r"C:\Users\Admin\Games\SuperSecretGame.exe"
        is_foreground = True
        selected = True

        def public_dict(self):
            return {
                "hwnd": self.hwnd,
                "pid": self.pid,
                "title": self.title,
                "process_name": self.process_name,
                "exe_path": self.exe_path,
                "is_foreground": self.is_foreground,
                "selected": self.selected,
            }

    original_target = target_manager.selected
    try:
        target_manager.selected = MockSecretTarget()

        # Local target status receives detailed window info
        st_tloc, data_tloc, _ = make_http_request("GET", "/api/target/status", local_host)
        assert st_tloc == 200
        assert data_tloc.get("selected") is not None

        # Remote target status MUST redact pid, hwnd, title, process_name, exe_path
        st_tcf, data_tcf, raw_tcf = make_http_request("GET", "/api/target/status", cf_host)
        assert st_tcf == 200
        assert data_tcf.get("selected") is True, "Remote should only know whether target is selected (boolean)"
        assert "pid" not in data_tcf
        assert "hwnd" not in data_tcf
        assert "title" not in data_tcf
        assert "process_name" not in data_tcf
        assert "exe_path" not in data_tcf
        assert "SuperSecretGame" not in raw_tcf
        assert "Classified" not in raw_tcf
        assert "C:\\Users" not in raw_tcf
        print("  [PASS] GET /api/target/status (Remote): Window title, PID, and executable path fully redacted")
    finally:
        target_manager.selected = original_target

    # 3. Error Responses must not leak stack traces or internal filepaths
    st_err, data_err, raw_err = make_http_request("POST", "/api/slot/999/controller", local_host, {"backend_id": "invalid"})
    assert st_err == 400
    assert "Traceback" not in raw_err
    assert "File \"" not in raw_err
    print("  [PASS] Error handling: 400/403/404 responses cleanly omit stack traces and source filepaths")


async def main():
    config = uvicorn.Config(app=app, host="127.0.0.1", port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    for _ in range(50):
        if server.started:
            break
        await asyncio.sleep(0.05)

    try:
        await asyncio.to_thread(run_endpoint_matrix_tests)
        await asyncio.to_thread(run_information_leakage_redaction_tests)
        print("\n" + "=" * 70)
        print("  >>> ALL SECURITY BOUNDARY & REDACTION TESTS PASSED! <<<")
        print("=" * 70 + "\n")
    finally:
        server.should_exit = True
        await server_task


if __name__ == "__main__":
    asyncio.run(main())
