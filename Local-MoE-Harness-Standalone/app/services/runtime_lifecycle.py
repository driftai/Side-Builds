from __future__ import annotations

from .model_registry import ModelRegistryError

try:
    import os
    _WINDOWS = os.name == "nt"
finally:
    del os

if _WINDOWS:
    from .runtime_lifecycle_windows import RuntimeLifecycle as _PlatformRuntimeLifecycle
else:
    from .runtime_lifecycle_linux import RuntimeLifecycle as _PlatformRuntimeLifecycle


class RuntimeLifecycle(_PlatformRuntimeLifecycle):
    """Platform facade with clean-checkout behavior shared by Linux and Windows."""

    async def ensure_started(self) -> dict:
        selected = self.registry.selected_model_id()
        try:
            self.registry.require_selectable_installed(selected)
        except ModelRegistryError:
            local = self.local_status()
            self.startup_stage = "waiting_for_model"
            self.last_error = (
                f"No installed selectable model is ready to start ({selected}). "
                "Install a trusted registry model or link its existing checkpoint location from the local web UI."
            )
            return {
                **local,
                "started": False,
                "already_reachable": False,
                "health_status": "offline",
                "error": self.last_error,
            }
        return await super().ensure_started()


__all__ = ["RuntimeLifecycle"]
