from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .model_registry_base import (
    ModelRecord,
    ModelRegistry as BaseModelRegistry,
    ModelRegistryError,
)


class ModelRegistry(BaseModelRegistry):
    """Trusted registry plus platform-specific public-release compatibility policy."""

    def __init__(self, root: Path, **kwargs: Any) -> None:
        super().__init__(root, **kwargs)
        self.platform_name = "windows" if os.name == "nt" else "linux"
        self.platform_policy_path = self.root / "config" / "platform-policy.json"
        self._platform_policy = self._load_platform_policy()
        self._apply_platform_policy()

    def _load_platform_policy(self) -> dict[str, Any]:
        try:
            data = json.loads(self.platform_policy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return {}
        return data

    def _apply_platform_policy(self) -> None:
        policy = self._platform_policy.get(self.platform_name, {})
        if not isinstance(policy, dict):
            return
        models = policy.get("models", {})
        if not isinstance(models, dict):
            return
        for model_id, overrides in models.items():
            if model_id not in self._models or not isinstance(overrides, dict):
                continue
            record = self._models[model_id]
            if "selectable" in overrides:
                record.data["selectable"] = bool(overrides["selectable"])
            if isinstance(overrides.get("validation"), str):
                record.data["validation"] = overrides["validation"]
            if isinstance(overrides.get("support"), str):
                record.data["platform_support"] = overrides["support"]
            note = overrides.get("note")
            if isinstance(note, str) and note:
                base_note = str(record.data.get("notes") or "")
                record.data["notes"] = f"{note} {base_note}".strip()

        default = self._models.get(self.default_model_id)
        if default is None or not default.selectable:
            raise ModelRegistryError(
                f"default model {self.default_model_id!r} is blocked on {self.platform_name}"
            )

    def public_models(self, *, active_model_id: str | None = None) -> list[dict[str, Any]]:
        result = super().public_models(active_model_id=active_model_id)
        by_id = {record.id: record for record in self.records()}
        for item in result:
            record = by_id[item["id"]]
            item["host_platform"] = self.platform_name
            item["platform_support"] = record.data.get(
                "platform_support",
                "validated-project-path" if self.platform_name == "linux" else "unknown",
            )
        return result


__all__ = ["ModelRecord", "ModelRegistry", "ModelRegistryError"]
