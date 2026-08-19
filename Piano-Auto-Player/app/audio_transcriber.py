from __future__ import annotations
import dataclasses
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse
from .audio_note_cleanup import preset_for, preset_keys
from .audio_engine import transcribe_audio
from .hifi_piano import probe_hifi
from .piano_layout import normalize_layout
from .performance_notation import performance_to_sheet
from .source_discovery import is_supported_media_url
from .youtube_access import (
    browser_diagnostic, clear_saved_session, load_saved_session,
    parse_session_cookies, profile_inventory, save_saved_session, saved_session_status, youtube_attempts,
)
_ALLOWED_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "music.youtube.com", "youtu.be"}
_ALLOWED_ACCESS = {"auto", "anonymous", "chrome", "edge", "firefox", "session"}
_ALLOWED_ENGINES = {"auto_hifi", "transkun", "basic_pitch"}
_AUDIO_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm", ".opus", ".aac")
_MIN_DENO = (2, 3, 0)
_MIN_NODE = (22, 0, 0)


@dataclasses.dataclass(frozen=True)
class DownloadedAudio:
    source_url: str
    title: str
    path: Path
    audio_format: str
    method: str = "direct"
    duration: float | None = None

    def __iter__(self):
        return iter((self.title, self.path, self.method))


class YouTubePianoTranscriber:
    """yt-dlp -> Basic Pitch -> timed-performance pipeline."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.venv = self.root / ".youtube-piano-venv"
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._session_cookies, self._session_summary = load_saved_session(self.root)

    def set_session_cookies(self, raw_text: str, persist: bool = True) -> dict:
        netscape, summary = parse_session_cookies(raw_text)
        if not summary.get("total_cookies", 0):
            raise ValueError("No usable cookies were found in the pasted session text.")
        with self._lock:
            self._session_cookies = netscape
            self._session_summary = summary
        if persist:
            save_saved_session(self.root, netscape)
        return saved_session_status(self.root, summary)

    def clear_session_cookies(self) -> dict:
        with self._lock:
            self._session_cookies = ""
            self._session_summary = {"total_cookies": 0, "has_account_cookies": False, "account_cookie_names": []}
        clear_saved_session(self.root)
        return self._session_summary

    def session_status(self) -> dict:
        with self._lock:
            return saved_session_status(self.root, self._session_summary)

    def diagnostics(self, url: str = "") -> dict:
        with self._lock:
            session = dict(self._session_summary)
        return {
            "dependencies": self.dependencies(),
            "profiles": profile_inventory(),
            "session": session,
            "windows_app_bound_encryption_active": True,
            "target_url": url,
        }

    def dependencies(self) -> dict:
        python = self._venv_python()
        basic_pitch = self._basic_pitch_exe()
        runtime = self._js_runtime()
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        po_provider = self._package_version("yt-dlp-getpot-wpc") if python else ""
        yt_dlp_version = self._package_version("yt-dlp") if python else ""
        hifi = probe_hifi(self.root)
        return {
            "ready": bool(python and basic_pitch and ffmpeg and ffprobe and runtime),
            "venv": bool(python),
            "basic_pitch": bool(basic_pitch),
            "ffmpeg": bool(ffmpeg),
            "ffprobe": bool(ffprobe),
            "js_runtime": bool(runtime),
            "js_runtime_name": runtime[0] if runtime else "",
            "js_runtime_version": runtime[2] if runtime else "",
            "js_runtime_issue": "" if runtime else self._runtime_issue(),
            "yt_dlp_version": yt_dlp_version,
            "po_provider": bool(po_provider),
            "po_provider_name": "WPC" if po_provider else "",
            "po_provider_version": po_provider,
            "setup_script": "setup-youtube-piano.bat", "hifi_ready": bool(hifi.get("ready")), "hifi_version": hifi.get("version", ""), "hifi_device": hifi.get("device", ""), "hifi_issue": hifi.get("issue", ""),
        }

    def start(self, url: str, access: str = "auto", title_hint: str = "", quality: str = "rhythm_accurate", layout: str = "61", engine: str = "auto_hifi") -> dict:
        url = self._validated_url(url)
        access = self._validated_access(access)
        title_hint = re.sub(r"\s+", " ", str(title_hint or "")).strip()[:180]
        quality = str(quality or "rhythm_accurate").strip().lower()
        if quality not in preset_keys():
            quality = "rhythm_accurate"
        layout = normalize_layout(layout)
        engine = str(engine or "auto_hifi").strip().lower(); engine = engine if engine in _ALLOWED_ENGINES else "auto_hifi"
        deps = self.dependencies()
        if not deps["ready"]:
            missing = [name for name in ("venv", "basic_pitch", "ffmpeg", "ffprobe", "js_runtime") if not deps[name]]
            detail = f" {deps['js_runtime_issue']}" if deps.get("js_runtime_issue") else ""
            raise ValueError(
                f"YouTube-to-Piano setup needs repair ({', '.join(missing)} missing).{detail} "
                "Run setup-youtube-piano.bat once, then restart start.bat."
            )
        job_id = uuid.uuid4().hex[:12]
        job = {"id": job_id, "status": "queued", "message": "Queued", "url": url, "access": access, "title_hint": title_hint, "quality": quality, "layout": layout, "engine": engine, "created_at": time.time()}
        with self._lock:
            self._jobs[job_id] = job
            self._trim_jobs()
        threading.Thread(target=self._run, args=(job_id, url, access, title_hint, quality, layout, engine), name=f"youtube-piano-{job_id}", daemon=True).start()
        return dict(job)

    def status(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(str(job_id))
            if not job:
                raise ValueError("Unknown YouTube transcription job.")
            return dict(job)

    def _set(self, job_id: str, **values) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].update(values)

    def _run(self, job_id: str, url: str, access: str = "auto", title_hint: str = "", quality: str = "rhythm_accurate", layout: str = "61", engine: str = "auto_hifi") -> None:
        try:
            python = self._venv_python()
            basic_pitch = self._basic_pitch_exe()
            if not python or not basic_pitch:
                raise RuntimeError("YouTube-to-Piano environment disappeared; rerun setup-youtube-piano.bat.")
            with tempfile.TemporaryDirectory(prefix="piano-youtube-") as temp_name:
                temp = Path(temp_name)
                self._set(job_id, status="resolving", message="Resolving media stream…")
                artifact = self._download_audio(job_id, python, url, temp, access, title_hint)
                if not isinstance(artifact, DownloadedAudio):
                    title, audio_file, method = artifact
                    artifact = DownloadedAudio(source_url=url, title=title, path=audio_file, audio_format="wav", method=method)
                preset = preset_for(quality)
                self._set(job_id, status="transcribing", message=f"Transcribing · {preset.label}… · {artifact.method}", title=artifact.title)

                self._set(job_id, status="importing", message=f"Cleaning timing and piano notes… · {preset.label}")
                hifi = probe_hifi(self.root)
                performance, stats = transcribe_audio(
                    self._run_checked, python, basic_pitch, artifact.path, temp, preset, layout, engine, str(hifi.get("python") or ""), str(hifi.get("device") or "cpu")
                )
                diagnostics = {key: value for key, value in stats.items() if key.startswith("hifi_")}
                song = {
                    "title": artifact.title,
                    "artist": "",
                    "sheet": performance_to_sheet(performance),
                    "performance": performance,
                    "source": ("YouTube" if self._is_youtube_url(url) else "Public media") + " → " + ("Hi-Fi piano" if stats.get("transcription_engine") in {"transkun", "hifi_fusion"} else "Basic Pitch"),
                    "source_url": url,
                    "timing_profile": "youtube_basic_pitch",
                    "fidelity": "transcribed_audio_cleaned" if preset.key != "raw" else "transcribed_audio",
                    "transcription_quality": preset.key,
                    "transcription_quality_label": preset.label,
                    "youtube_access_method": artifact.method,
                    "transcription_diagnostics": diagnostics,
                    **stats,
                }
                self._set(job_id, status="complete", message="Piano transcription ready", result=song)
        except Exception as exc:
            self._set(job_id, status="error", message=str(exc))

    def _download_audio(self, job_id: str, python: str, url: str, temp: Path, access: str, title_hint: str = "") -> DownloadedAudio:
        if not self._is_youtube_url(url):
            return self._download_public_media(job_id, python, url, temp, title_hint)
        errors: list[str] = []
        challenge = self._challenge_args()
        ffmpeg_args = self._ffmpeg_args()
        session_file = temp / "session_cookies.txt"
        disk_session, _ = load_saved_session(self.root)
        if disk_session:
            self.set_session_cookies(disk_session, persist=False)
        with self._lock:
            session_raw = self._session_cookies
        if session_raw:
            session_file.write_text(session_raw, encoding="utf-8")

        for label, extra in self._youtube_attempts(access, str(session_file) if session_file.exists() else ""):
            self._set(job_id, status="downloading", message=f"Downloading audio… · trying {label}")
            for path in temp.glob("*"):
                if path.is_file() and path != session_file:
                    path.unlink(missing_ok=True)
            command = [
                python, "-m", "yt_dlp", "--verbose", "--no-playlist", "--no-progress",
                "--no-simulate",
                "--print", "%(title)s",
                "--print", "after_move:%(filepath)s",
                "-f", "bestaudio/best", "-x", "--audio-format", "wav", "--audio-quality", "0",
                *ffmpeg_args,
                "-o", str(temp / "source.%(ext)s"), *challenge, *extra, url,
            ]
            completed = self._run_process(command, timeout=1800)
            artifact = self._discover_audio_artifact(temp, completed, url, label, title_hint)
            if completed.returncode == 0 and artifact:
                if "--cookies" in extra and session_file.is_file():
                    self.set_session_cookies(session_file.read_text(encoding="utf-8", errors="replace"))
                session_file.unlink(missing_ok=True)
                return artifact
            diagnostic = self._error_text(completed, produced_audio=bool(artifact), temp=temp)
            if "PO" in label or "po" in label:
                diagnostic = f"{diagnostic} · {self._po_provider_text(completed)}"
            if access in {"chrome", "edge", "firefox", "session"}:
                raw_log = "\n".join(part for part in (completed.stderr, completed.stdout) if part)
                diagnostic = f"{browser_diagnostic(raw_log, access)} · {diagnostic}"
            errors.append(f"{label}: {diagnostic}")
            self._set(job_id, diagnostics=errors[-4:])

        session_file.unlink(missing_ok=True)
        summary = " || ".join(errors[-3:]) if errors else "YouTube did not return downloadable audio."
        bot_challenge = any("not a bot" in err.lower() or "confirm you" in err.lower() for err in errors)
        if access in {"auto", "anonymous"} and bot_challenge:
            raise RuntimeError(
                "YouTube blocked anonymous access with a bot verification challenge ('Sign in to confirm you’re not a bot'). "
                "Switch YouTube access to 'Chrome session', 'Edge session', 'Firefox session', or import a Live Session."
            )
        if access == "session":
            raise RuntimeError(f"Live YouTube session could not unlock this video: {summary}")
        if access in {"chrome", "edge", "firefox"}:
            raise RuntimeError(
                f"The {access.title()} session could not unlock this exact video after testing its detected profiles and an HLS-only route. "
                f"The diagnostics below now describe the browser attempts themselves instead of anonymous fallbacks: {summary}"
            )
        raise RuntimeError(f"YouTube extraction failed: {summary}")

    def _download_public_media(self, job_id: str, python: str, url: str, temp: Path, title_hint: str = "") -> DownloadedAudio:
        self._set(job_id, status="downloading", message="Downloading alternate public audio…")
        ffmpeg_args = self._ffmpeg_args()
        command = [
            python, "-m", "yt_dlp", "--no-playlist", "--no-progress",
            "--no-simulate",
            "--print", "%(title)s",
            "--print", "after_move:%(filepath)s",
            "-f", "bestaudio/best", "-x", "--audio-format", "wav", "--audio-quality", "0",
            *ffmpeg_args,
            "-o", str(temp / "source.%(ext)s"), url,
        ]
        completed = self._run_process(command, timeout=1800)
        label = f"public source · {(urlparse(url).hostname or 'web')}"
        artifact = self._discover_audio_artifact(temp, completed, url, label, title_hint)
        if completed.returncode or not artifact:
            raise RuntimeError(f"Public media source could not be downloaded: {self._error_text(completed, produced_audio=bool(artifact), temp=temp)}")
        return artifact

    def _discover_audio_artifact(
        self, temp: Path, completed: subprocess.CompletedProcess, url: str, label: str, title_hint: str = ""
    ) -> DownloadedAudio | None:
        lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
        printed_title = lines[0] if lines else ""
        title = title_hint or printed_title or "Audio transcription"

        # 1. Inspect explicit filepath reported by yt-dlp after postprocessing
        for line in reversed(lines):
            try:
                candidate = Path(line)
                if candidate.exists() and candidate.is_file() and candidate.stat().st_size > 0:
                    return self._canonicalize_audio(candidate, url, title, label, temp)
            except (OSError, ValueError):
                continue

        # 2. Check for generated WAV files in job directory
        wavs = sorted(temp.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        if wavs and wavs[0].stat().st_size > 0:
            return DownloadedAudio(source_url=url, title=title, path=wavs[0], audio_format="wav", method=label)

        # 3. Check for any alternative audio formats and convert to canonical WAV
        for ext in _AUDIO_EXTENSIONS:
            found = sorted(temp.glob(f"*{ext}"), key=lambda p: p.stat().st_mtime, reverse=True)
            if found and found[0].stat().st_size > 0:
                return self._canonicalize_audio(found[0], url, title, label, temp)

        return None

    def _canonicalize_audio(self, audio_path: Path, url: str, title: str, label: str, temp: Path) -> DownloadedAudio:
        if audio_path.suffix.lower() == ".wav":
            return DownloadedAudio(source_url=url, title=title, path=audio_path, audio_format="wav", method=label)
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            target_wav = temp / f"{audio_path.stem}.wav"
            self._run_checked([ffmpeg, "-y", "-i", str(audio_path), "-vn", str(target_wav)])
            if target_wav.exists() and target_wav.stat().st_size > 0:
                return DownloadedAudio(source_url=url, title=title, path=target_wav, audio_format="wav", method=label)
        return DownloadedAudio(
            source_url=url, title=title, path=audio_path, audio_format=audio_path.suffix.lstrip(".").lower(), method=label
        )

    def _ffmpeg_args(self) -> list[str]:
        ffmpeg = shutil.which("ffmpeg")
        return ["--ffmpeg-location", str(Path(ffmpeg).parent)] if ffmpeg else []

    def _challenge_args(self) -> list[str]:
        runtime = self._js_runtime()
        if not runtime:
            raise RuntimeError("A supported YouTube JavaScript runtime is missing. Run setup-youtube-piano.bat, then restart start.bat.")
        name, path, _version = runtime
        return ["--js-runtimes", f"{name}:{path}"]

    @staticmethod
    def _youtube_attempts(access: str, session_cookie_path: str = "") -> list[tuple[str, list[str]]]:
        return youtube_attempts(access, session_cookie_path)

    def _run_checked(self, command: list[str]) -> None:
        completed = self._run_process(command, timeout=1800)
        if completed.returncode:
            raise RuntimeError(self._error_text(completed))

    def _run_process(self, command: list[str], timeout: int) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            command, cwd=self.root, capture_output=True, text=True,
            timeout=timeout, check=False, env=env, encoding="utf-8", errors="replace",
        )

    @staticmethod
    def _error_text(completed: subprocess.CompletedProcess, produced_audio: bool = False, temp: Path | None = None) -> str:
        text = "\n".join(part for part in (completed.stderr, completed.stdout) if part).strip()
        lines = [line.strip() for line in text.splitlines() if line.strip() and "Deprecated Feature:" not in line]
        errors = [line for line in lines if "ERROR:" in line]
        if errors:
            detail = " | ".join(errors[-3:])
        else:
            signals = ("warning:", "player response", "playability", "po token", "no video formats", "sign in", "unavailable", "cookies", "format")
            meaningful = [line for line in lines if any(token in line.lower() for token in signals)]
            detail = " | ".join(meaningful[-5:] or lines[-6:] or ["External command failed."])
        suffix = []
        if completed.returncode:
            suffix.append(f"exit {completed.returncode}")
        elif not produced_audio:
            files_in_temp = [p.name for p in temp.glob("*")] if temp and temp.exists() else []
            if files_in_temp:
                suffix.append(f"yt-dlp exited successfully but no audio file was created (found: {', '.join(files_in_temp)})")
            else:
                suffix.append("yt-dlp exited successfully but no WAV file was created")
        return f"{detail} · {'; '.join(suffix)}" if suffix else detail[-2200:]

    @staticmethod
    def _po_provider_text(completed: subprocess.CompletedProcess) -> str:
        text = "\n".join(part for part in (completed.stderr, completed.stdout) if part)
        provider_lines = [line.strip() for line in text.splitlines() if "PO Token Providers:" in line]
        if not provider_lines:
            return "WPC PO provider was not advertised in yt-dlp verbose output"
        latest = provider_lines[-1]
        return "WPC PO provider loaded" if "wpc" in latest.lower() else f"PO providers: {latest[-260:]}"

    def _venv_python(self) -> str:
        candidates = [self.venv / "Scripts" / "python.exe", self.venv / "bin" / "python"]
        return next((str(path) for path in candidates if path.exists()), "")

    def _basic_pitch_exe(self) -> str:
        candidates = [self.venv / "Scripts" / "basic-pitch.exe", self.venv / "Scripts" / "basic-pitch", self.venv / "bin" / "basic-pitch"]
        return next((str(path) for path in candidates if path.exists()), "")

    def _js_runtime(self) -> tuple[str, str, str] | None:
        for name, minimum in (("deno", _MIN_DENO), ("node", _MIN_NODE)):
            path = shutil.which(name)
            if not path:
                continue
            version = self._runtime_version(path)
            if version and version[:3] >= minimum:
                return name, path, ".".join(map(str, version[:3]))
        return None

    def _runtime_issue(self) -> str:
        issues = []
        for name, minimum in (("deno", _MIN_DENO), ("node", _MIN_NODE)):
            path = shutil.which(name)
            if not path:
                continue
            version = self._runtime_version(path)
            shown = ".".join(map(str, version[:3])) if version else "unknown"
            issues.append(f"{name} {shown} found; needs {'.'.join(map(str, minimum))}+")
        return "; ".join(issues) or "Deno 2.3+ or Node 22+ was not found."

    @staticmethod
    def _runtime_version(path: str) -> tuple[int, int, int] | None:
        try:
            completed = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        match = re.search(r"(?:v|deno\s+)?(\d+)\.(\d+)(?:\.(\d+))?", (completed.stdout or completed.stderr or ""), re.I)
        if not match:
            return None
        return tuple(int(value or 0) for value in match.groups())

    @staticmethod
    def _validated_url(url: str) -> str:
        value = str(url or "").strip()
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in {"http", "https"} or not (host in _ALLOWED_YOUTUBE_HOSTS or is_supported_media_url(value)):
            raise ValueError("Paste a supported YouTube or public audio/video URL.")
        return value

    @staticmethod
    def _is_youtube_url(url: str) -> bool:
        return (urlparse(str(url or "")).hostname or "").lower() in _ALLOWED_YOUTUBE_HOSTS

    def _package_version(self, package: str) -> str:
        python = self._venv_python()
        if not python:
            return ""
        completed = subprocess.run(
            [python, "-c", f"import importlib.metadata as m; print(m.version({package!r}))"],
            capture_output=True, text=True, timeout=8, check=False,
        )
        return (completed.stdout or "").strip() if completed.returncode == 0 else ""

    @staticmethod
    def _validated_access(access: str) -> str:
        value = str(access or "auto").strip().lower()
        if value not in _ALLOWED_ACCESS:
            raise ValueError("Unknown YouTube access mode.")
        return value

    def _trim_jobs(self) -> None:
        if len(self._jobs) <= 20:
            return
        for job_id, _job in sorted(self._jobs.items(), key=lambda item: item[1].get("created_at", 0))[:-20]:
            self._jobs.pop(job_id, None)
