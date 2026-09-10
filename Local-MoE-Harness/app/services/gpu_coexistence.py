from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class GpuSample:
    util_pct: float
    memory_used_mb: float
    memory_total_mb: float
    source: str
    sampled_at: float


class GpuCoexistenceManager:
    """Share the Windows-host GPU with other apps without permanently slowing inference.

    Pressure is sampled while the harness is idle so FreeToken's own work does not cause
    mode changes. Under sustained external pressure the manager live-shrinks only the MoE
    expert cache; the 8K KV pool stays untouched. Cache rebuilds are serialized with chat
    requests and are never issued mid-generation.
    """

    def __init__(
        self,
        adapter: Any,
        settings: dict[str, Any],
        runtime_lifecycle: Any = None,
    ):
        self.adapter = adapter
        self.settings = settings
        self.runtime_lifecycle = runtime_lifecycle
        self.enabled = bool(settings.get("gpu_coexistence_enabled", True))
        self.enter_util_pct = float(settings.get("gpu_coexistence_enter_util_pct", 70))
        self.exit_util_pct = float(settings.get("gpu_coexistence_exit_util_pct", 25))
        self.enter_samples = max(1, int(settings.get("gpu_coexistence_enter_samples", 3)))
        self.exit_samples = max(1, int(settings.get("gpu_coexistence_exit_samples", 6)))
        self.poll_seconds = max(0.5, float(settings.get("gpu_coexistence_poll_seconds", 2)))
        self.transition_cooldown_seconds = max(
            0.0, float(settings.get("gpu_coexistence_transition_cooldown_seconds", 20))
        )
        self.cache_ratio = min(
            1.0, max(0.1, float(settings.get("gpu_coexistence_cache_ratio", 0.70)))
        )
        self.normal_timeout_seconds = float(settings.get("request_timeout_seconds", 300))
        self.coexistence_timeout_seconds = float(
            settings.get("gpu_coexistence_request_timeout_seconds", 1200)
        )
        self.telemetry_timeout_seconds = max(
            1.0, float(settings.get("gpu_coexistence_telemetry_timeout_seconds", 4))
        )
        self.rebuild_timeout_seconds = max(
            10.0, float(settings.get("gpu_coexistence_rebuild_timeout_seconds", 180))
        )

        self.mode = "normal"
        self.pending_transition: str | None = None
        self.normal_moe_slots: int | None = int(settings.get("gpu_coexistence_normal_moe_slots", 736))
        self.active_moe_slots: int | None = None
        self.minimum_moe_slots: int | None = None
        self.active_requests = 0
        self.model_switching = False

        self.latest_sample: GpuSample | None = None
        self.telemetry_error: str | None = None
        self.last_transition_error: str | None = None
        self.last_transition_at: float | None = None
        self._last_transition_monotonic = 0.0
        self._enter_count = 0
        self._exit_count = 0

        self._task: asyncio.Task | None = None
        self._state_lock = asyncio.Lock()
        self._stopping = False

    async def start(self) -> None:
        if not self.enabled or (self._task and not self._task.done()):
            return
        startup_mode = (
            getattr(self.runtime_lifecycle, "startup_gpu_mode", "normal")
            if self.runtime_lifecycle
            else "normal"
        )
        if startup_mode.startswith("coexistence"):
            self.mode = "coexistence"
            try:
                cache_doc = await self.adapter.cache_status(timeout_seconds=5.0)
                geometry = (cache_doc or {}).get("geometry") or {}
                self.active_moe_slots = int(geometry.get("moe_cache_size") or 616)
            except Exception:
                self.active_moe_slots = 616
        self._stopping = False
        self._task = asyncio.create_task(self._monitor_loop(), name="gpu-coexistence")

    async def stop(self) -> None:
        self._stopping = True
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _monitor_loop(self) -> None:
        while not self._stopping:
            try:
                sample = await self._sample_gpu()
                self.latest_sample = sample
                self.telemetry_error = None
                runtime = await self.adapter.status()
                if not runtime.get("ready"):
                    # Model loading/warmup can saturate the GPU; never classify that as
                    # an external workload.
                    self._enter_count = 0
                    self._exit_count = 0
                elif self.active_requests == 0:
                    await self._record_idle_sample(sample)
                else:
                    # Do not let FreeToken's own GPU work look like an external workload.
                    self._enter_count = 0
                    self._exit_count = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.telemetry_error = str(exc)
                logger.debug("GPU coexistence telemetry failed: %s", exc)
            await asyncio.sleep(self.poll_seconds)

    async def _record_idle_sample(self, sample: GpuSample) -> None:
        if self.mode == "normal" and sample.util_pct < self.enter_util_pct:
            if self.pending_transition == "coexistence":
                self.pending_transition = None
        elif self.mode == "coexistence" and sample.util_pct > self.exit_util_pct:
            if self.pending_transition == "normal":
                self.pending_transition = None

        if sample.util_pct >= self.enter_util_pct:
            self._enter_count += 1
            self._exit_count = 0
        elif sample.util_pct <= self.exit_util_pct:
            self._exit_count += 1
            self._enter_count = 0
        else:
            self._enter_count = 0
            self._exit_count = 0

        startup_mode = getattr(self.runtime_lifecycle, "startup_gpu_mode", "normal") if self.runtime_lifecycle else "normal"
        should_restore_graph = bool(
            self.runtime_lifecycle
            and hasattr(self.runtime_lifecycle, "normal_profile_uses_graph")
            and self.runtime_lifecycle.normal_profile_uses_graph()
        )
        if (
            startup_mode == "coexistence-eager"
            and should_restore_graph
            and self.active_requests == 0
            and self._exit_count >= self.exit_samples
        ):
            if hasattr(self.runtime_lifecycle, "restart_normal"):
                logger.info(
                    "External GPU load cleared; restarting FreeToken from emergency eager mode into normal graph mode"
                )
                self._exit_count = 0
                await self.runtime_lifecycle.restart_normal()
                self.mode = "normal"
                return

        if self.mode == "normal" and self._enter_count >= self.enter_samples:
            await self._request_transition("coexistence")
            self._enter_count = 0
        elif self.mode == "coexistence" and self._exit_count >= self.exit_samples:
            await self._request_transition("normal")
            self._exit_count = 0

        if self.pending_transition and self.active_requests == 0:
            await self._request_transition(self.pending_transition)

    async def _request_transition(self, target: str) -> None:
        if not self.enabled or target not in {"normal", "coexistence"}:
            return

        async with self._state_lock:
            if self.active_requests:
                self.pending_transition = target
                return

            now = time.monotonic()
            if (
                self.last_transition_at is not None
                and now - self._last_transition_monotonic < self.transition_cooldown_seconds
            ):
                self.pending_transition = target
                return

            try:
                cache_doc = await self.adapter.cache_status(timeout_seconds=10.0)
                geometry = (cache_doc or {}).get("geometry") or {}
                current = int(geometry.get("moe_cache_size") or 0)
                if current <= 0:
                    self.pending_transition = target
                    self.last_transition_error = "FreeToken did not report a live MoE cache size."
                    return

                if self.normal_moe_slots is None:
                    self.normal_moe_slots = current

                self.active_moe_slots = current
                limits = ((geometry.get("limits") or {}).get("moe_experts") or {})
                minimum = int(limits.get("min") or 1)
                self.minimum_moe_slots = minimum

                if target == "coexistence":
                    desired = max(minimum, int(round(self.normal_moe_slots * self.cache_ratio)))
                    desired = min(self.normal_moe_slots, desired)
                else:
                    desired = self.normal_moe_slots

                if desired != current:
                    result = await self.adapter.rebuild_moe_cache(
                        desired, wait_seconds=self.rebuild_timeout_seconds
                    )
                    if (result or {}).get("status") != "ok":
                        raise RuntimeError(
                            (result or {}).get("error")
                            or f"FreeToken cache rebuild returned {(result or {}).get('status')!r}"
                        )
                    refreshed = await self.adapter.cache_status(timeout_seconds=10.0)
                    refreshed_geometry = (refreshed or {}).get("geometry") or {}
                    self.active_moe_slots = int(
                        refreshed_geometry.get("moe_cache_size") or desired
                    )
                else:
                    self.active_moe_slots = current

                self.mode = target
                self.pending_transition = None
                self.last_transition_error = None
                self._last_transition_monotonic = now
                self.last_transition_at = time.time()
                logger.info(
                    "GPU coexistence mode -> %s (MoE slots %s -> %s)",
                    target,
                    current,
                    self.active_moe_slots,
                )
            except Exception as exc:
                self.pending_transition = target
                self.last_transition_error = str(exc)
                logger.warning("GPU coexistence transition to %s failed: %s", target, exc)

    async def reserve_model_switch(self) -> None:
        """Atomically exclude new generation while a model restart is pending."""
        async with self._state_lock:
            if self.model_switching:
                raise RuntimeError("A model switch is already in progress.")
            if self.active_requests:
                raise RuntimeError("Cannot switch models during an active request.")
            self.model_switching = True
            self.pending_transition = None

    async def release_model_switch(self) -> None:
        async with self._state_lock:
            self.model_switching = False

    def configure_runtime_profile(
        self,
        normal_profile: dict[str, Any],
        busy_profile: dict[str, Any],
        *,
        active_profile_name: str,
    ) -> None:
        """Refresh cache/timeout policy after a successful cold model switch."""
        slots = normal_profile.get("moe_slots")
        self.normal_moe_slots = int(slots) if slots is not None else None
        self.normal_timeout_seconds = float(normal_profile["request_timeout"])
        self.coexistence_timeout_seconds = float(busy_profile["request_timeout"])
        self.mode = "coexistence" if active_profile_name == "busy" else "normal"
        self.pending_transition = None
        self.active_moe_slots = None
        self.minimum_moe_slots = None
        self.last_transition_error = None
        self._enter_count = 0
        self._exit_count = 0

    async def _sample_gpu(self) -> GpuSample:
        query = (
            "--query-gpu=utilization.gpu,memory.used,memory.total "
            "--format=csv,noheader,nounits"
        )
        windows_command = (
            "nvidia-smi.exe "
            "--query-gpu=utilization.gpu,memory.used,memory.total "
            "--format=csv,noheader,nounits"
        )
        attempts = [
            (
                "windows-nvidia-smi",
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    windows_command,
                ],
            ),
            ("wsl-nvidia-smi", ["nvidia-smi", *query.split()]),
        ]

        errors: list[str] = []
        for source, command in attempts:
            try:
                output = await asyncio.to_thread(self._run_query, command)
                return self._parse_gpu_sample(output, source)
            except Exception as exc:
                errors.append(f"{source}: {exc}")
        raise RuntimeError("; ".join(errors))

    def _run_query(self, command: list[str]) -> str:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=self.telemetry_timeout_seconds,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or f"exit {proc.returncode}").strip())
        return proc.stdout

    @staticmethod
    def _parse_gpu_sample(output: str, source: str) -> GpuSample:
        line = next((item.strip() for item in output.splitlines() if item.strip()), "")
        if not line:
            raise ValueError("empty nvidia-smi output")
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3:
            raise ValueError(f"unexpected nvidia-smi output: {line!r}")
        return GpuSample(
            util_pct=float(parts[0]),
            memory_used_mb=float(parts[1]),
            memory_total_mb=float(parts[2]),
            source=source,
            sampled_at=time.time(),
        )

    async def _refresh_sample_if_stale(self) -> None:
        sample = self.latest_sample
        if sample and time.time() - sample.sampled_at <= max(2.0, self.poll_seconds * 2):
            return
        try:
            sample = await self._sample_gpu()
            self.latest_sample = sample
            self.telemetry_error = None
            runtime = await self.adapter.status()
            if runtime.get("ready") and self.active_requests == 0:
                await self._record_idle_sample(sample)
        except Exception as exc:
            self.telemetry_error = str(exc)

    def current_request_timeout_seconds(self) -> float:
        sample = self.latest_sample
        pressure_now = bool(sample and sample.util_pct >= self.enter_util_pct)
        if self.mode == "coexistence" or pressure_now:
            return self.coexistence_timeout_seconds
        return self.normal_timeout_seconds

    @asynccontextmanager
    async def request_scope(self) -> AsyncIterator[float]:
        if self.enabled:
            await self._refresh_sample_if_stale()

        async with self._state_lock:
            if self.model_switching:
                raise RuntimeError("Model switch in progress; generation is temporarily disabled.")
            self.active_requests += 1
            timeout_seconds = self.current_request_timeout_seconds()

        try:
            yield timeout_seconds
        finally:
            pending: str | None
            async with self._state_lock:
                self.active_requests = max(0, self.active_requests - 1)
                pending = self.pending_transition if self.active_requests == 0 else None
            if pending:
                await self._request_transition(pending)

    def snapshot(self) -> dict[str, Any]:
        sample = asdict(self.latest_sample) if self.latest_sample else None
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "startup_gpu_mode": getattr(self.runtime_lifecycle, "startup_gpu_mode", "normal") if self.runtime_lifecycle else "normal",
            "gpu": sample,
            "telemetry_error": self.telemetry_error,
            "normal_moe_slots": self.normal_moe_slots,
            "active_moe_slots": self.active_moe_slots,
            "minimum_moe_slots": self.minimum_moe_slots,
            "active_requests": self.active_requests,
            "model_switching": self.model_switching,
            "pending_transition": self.pending_transition,
            "request_timeout_seconds": self.current_request_timeout_seconds(),
            "enter_util_pct": self.enter_util_pct,
            "exit_util_pct": self.exit_util_pct,
            "cache_ratio": self.cache_ratio,
            "last_transition_at": self.last_transition_at,
            "last_transition_error": self.last_transition_error,
        }
