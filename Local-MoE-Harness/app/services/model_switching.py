from __future__ import annotations

import asyncio
import time
from typing import Any

from .model_registry import ModelRegistry, ModelRegistryError


class ModelSwitchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        restored_model_id: str | None = None,
        client_error: bool = False,
    ) -> None:
        super().__init__(message)
        self.restored_model_id = restored_model_id
        self.client_error = client_error


class ModelSwitchCoordinator:
    """Serialize cold model replacement and restore the last known-good model."""

    def __init__(
        self,
        registry: ModelRegistry,
        lifecycle: Any,
        adapter: Any,
        gpu_manager: Any,
        conversation_store: Any,
    ) -> None:
        self.registry = registry
        self.lifecycle = lifecycle
        self.adapter = adapter
        self.gpu_manager = gpu_manager
        self.conversation_store = conversation_store
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = {
            "status": "idle",
            "stage": "idle",
            "target_model_id": None,
            "previous_model_id": None,
            "active_model_id": lifecycle.active_model_id,
            "error": None,
            "restored_model_id": None,
            "started_at": None,
            "finished_at": None,
        }

    def snapshot(self) -> dict[str, Any]:
        state = dict(self._state)
        state["active_model_id"] = self.lifecycle.active_model_id
        if state["status"] == "switching":
            state["stage"] = self.lifecycle.startup_stage or state["stage"]
        return state

    def _set_state(self, **values: Any) -> None:
        self._state.update(values)

    def _configure_gpu(self, model_id: str) -> None:
        active_profile = self.lifecycle.active_profile_name or "normal"
        self.gpu_manager.configure_runtime_profile(
            self.registry.profile(model_id, "normal"),
            self.registry.profile(model_id, "busy"),
            active_profile_name=active_profile,
        )

    async def _restore(self, candidates: list[str]) -> str | None:
        await self.lifecycle.stop_managed()
        for model_id in candidates:
            try:
                self.registry.require_selectable_installed(model_id)
                result = await self.lifecycle.start_model(
                    model_id, wait_until_ready=True
                )
                if not result.get("ready"):
                    await self.lifecycle.stop_managed()
                    continue
                self.registry.persist_selection(model_id)
                self._configure_gpu(model_id)
                return model_id
            except Exception:
                await self.lifecycle.stop_managed()
        return None

    async def switch(self, model_id: str) -> dict[str, Any]:
        """Cold-switch to a trusted installed model with deterministic rollback."""
        try:
            target = self.registry.require_selectable_installed(model_id)
        except ModelRegistryError as exc:
            raise ModelSwitchError(str(exc), client_error=True) from exc

        async with self._lock:
            previous_id = (
                self.lifecycle.active_model_id or self.registry.selected_model_id()
            )
            if target.id == previous_id:
                runtime = await self.adapter.status()
                if runtime.get("ready"):
                    return {**self.snapshot(), "status": "ready", "unchanged": True}

            try:
                await self.gpu_manager.reserve_model_switch()
            except RuntimeError as exc:
                raise ModelSwitchError(str(exc), client_error=True) from exc

            started_at = time.time()
            self._set_state(
                status="switching",
                stage="stopping_previous",
                target_model_id=target.id,
                previous_model_id=previous_id,
                error=None,
                restored_model_id=None,
                started_at=started_at,
                finished_at=None,
            )
            try:
                await self.gpu_manager.stop()
                await self.lifecycle.stop_managed()
                self._set_state(stage="starting_target")
                result = await self.lifecycle.start_model(
                    target.id, wait_until_ready=True
                )
                if not result.get("ready"):
                    raise RuntimeError(
                        result.get("error") or "Target runtime did not become ready."
                    )

                self._set_state(stage="committing_selection")
                self.registry.persist_selection(target.id)
                cleared_sessions = self.conversation_store.reset_all()
                self._configure_gpu(target.id)
                await self.gpu_manager.start()
                self._set_state(
                    status="ready",
                    stage="ready",
                    active_model_id=target.id,
                    error=None,
                    finished_at=time.time(),
                )
                return {
                    **self.snapshot(),
                    "cleared_conversation_sessions": cleared_sessions,
                }
            except Exception as exc:
                self._set_state(stage="restoring_previous", error=str(exc))
                candidates = [previous_id]
                if self.registry.default_model_id not in candidates:
                    candidates.append(self.registry.default_model_id)
                restored_id = await self._restore(candidates)
                await self.gpu_manager.start()
                self._set_state(
                    status="failed",
                    stage="restored" if restored_id else "restore_failed",
                    active_model_id=restored_id,
                    restored_model_id=restored_id,
                    finished_at=time.time(),
                )
                message = f"Model switch to {target.id} failed: {exc}"
                if restored_id:
                    message += f" Previous stable model {restored_id} was restored."
                else:
                    message += " The previous and default models could not be restored."
                raise ModelSwitchError(
                    message, restored_model_id=restored_id
                ) from exc
            finally:
                await self.gpu_manager.release_model_switch()
