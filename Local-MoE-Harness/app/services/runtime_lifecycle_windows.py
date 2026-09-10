from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import psutil

from .model_registry import ModelRecord
from .runtime_lifecycle_linux import RuntimeLifecycle as LinuxRuntimeLifecycle


class RuntimeLifecycle(LinuxRuntimeLifecycle):
    """Native-Windows FreeToken lifecycle using only project-local runtime files."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.script = self.root / "scripts" / "run-freetoken-windows.ps1"
        self.venv = self.root / ".venvs" / "freetoken"
        self.ft_python = self.venv / "Scripts" / "python.exe"
        self.runtime_dir = self.root / "runtime" / "freetoken"

    @staticmethod
    def _pid_alive(pid: int | None) -> bool:
        if not pid or pid <= 1:
            return False
        try:
            return psutil.Process(pid).is_running()
        except psutil.Error:
            return False

    def _pid_is_managed_runtime(self, pid: int) -> bool:
        try:
            process = psutil.Process(pid)
            command = " ".join(process.cmdline()).lower()
        except psutil.Error:
            return False
        root = str(self.root).lower()
        return root in command and (
            "run-freetoken-windows.ps1" in command
            or (
                str(self.ft_python).lower() in command
                and "freetoken.cli" in command
                and " serve " in f" {command} "
            )
        )

    def local_status(self) -> dict[str, Any]:
        pid = self._read_pid()
        running = self._pid_alive(pid)
        if pid and not running:
            try:
                self.pid_path.unlink()
            except OSError:
                pass
            pid = None

        missing: list[str] = []
        if not self.script.is_file():
            missing.append(str(self.script))
        if not self.ft_python.is_file():
            missing.append(str(self.ft_python))

        return {
            "managed_pid": pid,
            "managed_running": running,
            "can_start": not missing,
            "missing": missing,
            "log_path": str(self.log_path),
            "startup_gpu_mode": self.startup_gpu_mode,
            "active_model_id": self.active_model_id,
            "active_profile": self.active_profile_name,
            "startup_stage": self.startup_stage,
            "last_error": self.last_error,
            "platform_runtime": "native-windows",
        }

    async def stop_managed(self) -> None:
        self.startup_stage = "stopping"
        pid = self._read_pid()
        if pid and self._pid_alive(pid):
            if not self._pid_is_managed_runtime(pid):
                self.last_error = (
                    f"Refusing to stop PID {pid}: it is not this harness's "
                    "project-local FreeToken process."
                )
                try:
                    self.pid_path.unlink()
                except OSError:
                    pass
                self.startup_stage = "stopped"
                return
            try:
                parent = psutil.Process(pid)
                processes = parent.children(recursive=True)
                processes.append(parent)
                for process in reversed(processes):
                    try:
                        process.terminate()
                    except psutil.Error:
                        pass
                _, alive = psutil.wait_procs(processes, timeout=10)
                for process in alive:
                    try:
                        process.kill()
                    except psutil.Error:
                        pass
            except psutil.Error:
                pass
        try:
            self.pid_path.unlink()
        except OSError:
            pass
        self.startup_stage = "stopped"

    def _process_args(self, record: ModelRecord) -> list[str]:
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.script),
            "-ModelPath",
            str(record.runtime_path),
            "-Port",
            str(self.port),
        ]

    async def _start_process(
        self,
        record: ModelRecord,
        environment: dict[str, str],
    ) -> dict[str, Any]:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.startup_stage = "loading_weights"
        self.last_error = None
        try:
            self._log_start_offset = self.log_path.stat().st_size
        except OSError:
            self._log_start_offset = 0

        args = self._process_args(record)
        log_file = self.log_path.open("ab", buffering=0)
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(self.root),
                stdout=log_file,
                stderr=asyncio.subprocess.STDOUT,
                env=environment,
                creationflags=creationflags,
            )
        finally:
            log_file.close()

        self.pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
        self.active_model_id = record.id
        await asyncio.sleep(0.35)
        if process.returncode is not None:
            try:
                self.pid_path.unlink()
            except OSError:
                pass
            self.last_error = (
                f"FreeToken exited immediately with code {process.returncode}. "
                f"Check {self.log_path}."
            )
            self.startup_stage = "failed"
            return {**self.local_status(), "started": False, "error": self.last_error}

        return {
            **self.local_status(),
            "started": True,
            "already_reachable": False,
            "health_status": "starting",
        }

    async def _existing_runtime(self) -> dict[str, Any] | None:
        existing = await super()._existing_runtime()
        if existing is None:
            return None
        pid = self._read_pid()
        if pid and self._pid_alive(pid) and self._pid_is_managed_runtime(pid):
            return existing
        self.active_model_id = None
        self.active_profile_name = None
        self.startup_stage = "blocked_external_runtime"
        self.last_error = (
            f"A FreeToken server is already reachable on port {self.port}, but it "
            "was not launched from this tool folder. Self-contained mode refuses "
            "to adopt external runtimes."
        )
        return None
