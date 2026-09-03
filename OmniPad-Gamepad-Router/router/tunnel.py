"""
Network and Cloudflare Quick-Tunnel Management.
Enables instant zero-config cross-city connections via trycloudflare.com
and local network discovery via LAN IP resolution.
"""

import asyncio
import atexit
import logging
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger("OmniPad.Tunnel")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_local_ips() -> List[str]:
    """Retrieve all non-loopback IPv4 addresses of this machine."""
    ips = []
    try:
        # Connect to an external address (doesn't send packets) to get primary interface IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip and primary_ip not in ("127.0.0.1", "0.0.0.0"):
            ips.append(primary_ip)
    except Exception:
        pass

    try:
        # Enumerate hostname addresses
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    return ips or ["127.0.0.1"]


class TunnelManager:
    """Manages Cloudflare Quick Tunnels (trycloudflare.com) via cloudflared.exe."""

    DEFAULT_PATHS = [
        os.path.join(PROJECT_ROOT, ".runtime", "bin", "cloudflared.exe"),
        shutil.which("cloudflared"),
        r"C:\Program Files (x86)\cloudflared\cloudflared.EXE",
        r"C:\Program Files\cloudflared\cloudflared.EXE",
        os.path.expanduser(r"~\AppData\Local\Programs\cloudflared\cloudflared.exe"),
    ]

    def __init__(self, local_port: int = 8000):
        self.local_port = local_port
        self.cloudflared_path: Optional[str] = self._find_cloudflared()
        self.process: Optional[subprocess.Popen] = None
        self.public_url: Optional[str] = None
        self.status: str = "stopped"  # "stopped", "starting", "active", "error"
        self.error_message: Optional[str] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._atexit_registered = False
        self._stop_lock = threading.Lock()

    def _find_cloudflared(self) -> Optional[str]:
        for p in self.DEFAULT_PATHS:
            if p and os.path.isfile(p):
                return p
        return None

    def is_available(self) -> bool:
        return self.cloudflared_path is not None

    def start(self, port: Optional[int] = None) -> bool:
        """Start the Cloudflare Quick Tunnel in background."""
        if port:
            self.local_port = port

        if not self.cloudflared_path:
            self.status = "error"
            self.error_message = "cloudflared.exe not found on system."
            logger.error(self.error_message)
            return False

        if self.process and self.process.poll() is None:
            logger.info("Cloudflare tunnel is already running: %s", self.public_url)
            return True

        self.status = "starting"
        self.public_url = None
        self.error_message = None
        self._stop_event.clear()

        cmd = [
            self.cloudflared_path,
            "tunnel",
            "--url",
            f"http://127.0.0.1:{self.local_port}"
        ]

        try:
            logger.info("Spawning cloudflared tunnel on port %d...", self.local_port)
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            self._reader_thread = threading.Thread(target=self._monitor_output, daemon=True)
            self._reader_thread.start()
            if not self._atexit_registered:
                atexit.register(self.stop)
                self._atexit_registered = True
            return True
        except Exception as e:
            self.status = "error"
            self.error_message = str(e)
            logger.exception("Failed to start cloudflared: %s", e)
            return False

    def _monitor_output(self) -> None:
        process = self.process
        if not process or not process.stdout:
            return

        url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        try:
            for line in iter(process.stdout.readline, ''):
                if self._stop_event.is_set():
                    break
                line_str = line.strip()
                if not line_str:
                    continue

                try:
                    logger.debug("[cloudflared] %s", line_str)
                except Exception:
                    pass

                if not self.public_url:
                    match = url_pattern.search(line_str)
                    if match:
                        self.public_url = match.group(0)
                        self.status = "active"
                        try:
                            logger.info(">>> CLOUDFLARE QUICK TUNNEL READY: %s <<<", self.public_url)
                        except Exception:
                            pass

            if process.poll() is not None and not self._stop_event.is_set():
                if self.status != "active":
                    self.status = "error"
                    self.error_message = "cloudflared process terminated unexpectedly."
        except (IOError, ValueError, OSError, AttributeError):
            # Stream can close while shutdown is underway.
            pass

    def stop(self) -> None:
        """Stop Cloudflare quickly and safely without blocking shutdown indefinitely."""
        with self._stop_lock:
            self._stop_event.set()
            proc = self.process
            reader = self._reader_thread
            self.process = None
            self._reader_thread = None

            if proc is not None:
                pid = proc.pid

                # Give cloudflared a brief chance to exit cleanly.
                try:
                    proc.terminate()
                except Exception:
                    pass

                try:
                    proc.wait(timeout=0.75)
                except (subprocess.TimeoutExpired, OSError):
                    pass

                # If it is still alive, kill only this process tree. Bound taskkill
                # so a broken Windows process cannot hold up OmniPad shutdown.
                if proc.poll() is None and os.name == 'nt' and pid:
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                            check=False,
                            timeout=1.5,
                        )
                    except (subprocess.TimeoutExpired, OSError, Exception):
                        pass

                try:
                    proc.kill()
                except Exception:
                    pass

            # Do not wait on the reader indefinitely. It is daemonized and will
            # naturally terminate once the cloudflared pipe closes.
            if reader and reader.is_alive() and reader is not threading.current_thread():
                reader.join(timeout=0.25)

            self.status = "stopped"
            self.public_url = None
            try:
                logger.info("Cloudflare tunnel stopped.")
            except Exception:
                pass

    def get_info(self) -> Dict[str, Any]:
        return {
            "available": self.is_available(),
            "status": self.status,
            "public_url": self.public_url,
            "error": self.error_message,
            "binary_path": self.cloudflared_path
        }
