from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .model_registry_base import (
    ModelRecord,
    ModelRegistry as BaseModelRegistry,
    ModelRegistryError,
)


class ModelRegistry(BaseModelRegistry):
    """Trusted registry plus platform policy and machine-local model locations."""

    def __init__(self, root: Path, **kwargs: Any) -> None:
        super().__init__(root, **kwargs)
        self.platform_name = "windows" if os.name == "nt" else "linux"
        self.platform_policy_path = self.root / "config" / "platform-policy.json"
        self.location_state_path = self.root / "state" / "model-locations.json"
        self._default_paths = {
            record.id: (record.local_path, record.runtime_path)
            for record in self.records()
        }
        self._location_overrides = self._load_location_overrides()
        self._location_errors: dict[str, str] = {}
        self._apply_location_overrides()
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

    def _load_location_overrides(self) -> dict[str, str]:
        try:
            data = json.loads(self.location_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return {}
        raw_models = data.get("models")
        if not isinstance(raw_models, dict):
            return {}
        return {
            str(model_id): path
            for model_id, path in raw_models.items()
            if isinstance(model_id, str) and isinstance(path, str) and path.strip()
        }

    def _location_paths(self, record: ModelRecord, raw_path: str) -> tuple[Path, Path]:
        value = os.path.expandvars(os.path.expanduser(raw_path.strip()))
        if not value or "\x00" in value:
            raise ModelRegistryError("Model location must be a non-empty absolute path")
        candidate = Path(value)
        if not candidate.is_absolute():
            raise ModelRegistryError("Model location must be an absolute path")
        candidate = candidate.resolve(strict=False)

        serve_file = record.data.get("serve_file")
        direct_file = bool(serve_file and candidate.name == serve_file)
        if candidate.exists() and candidate.is_file():
            if not direct_file:
                raise ModelRegistryError(
                    f"{record.id}: location must be a model directory"
                )
            local_path = candidate.parent.resolve(strict=False)
            runtime_path = candidate
        else:
            local_path = candidate
            runtime_path = (
                (local_path / str(serve_file)).resolve(strict=False)
                if serve_file
                else local_path
            )

        try:
            runtime_path.relative_to(local_path)
        except ValueError as exc:
            raise ModelRegistryError(
                f"{record.id}: runtime entrypoint must stay inside the linked model location"
            ) from exc
        return local_path, runtime_path

    def _record_at_location(self, record: ModelRecord, raw_path: str) -> ModelRecord:
        local_path, runtime_path = self._location_paths(record, raw_path)
        return ModelRecord(dict(record.data), local_path, runtime_path)

    def _apply_location_overrides(self) -> None:
        for model_id, raw_path in self._location_overrides.items():
            record = self._models.get(model_id)
            if record is None:
                continue
            try:
                self._models[model_id] = self._record_at_location(record, raw_path)
            except ModelRegistryError as exc:
                self._location_errors[model_id] = str(exc)

    def _write_location_overrides(self, overrides: dict[str, str]) -> None:
        self.location_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"schema_version": 1, "models": overrides},
            indent=2,
            sort_keys=True,
        ) + "\n"
        fd, temp_name = tempfile.mkstemp(
            prefix="model-locations.", suffix=".tmp", dir=self.location_state_path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.location_state_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def set_model_location(self, model_id: str, path: str) -> ModelRecord:
        record = self.require(model_id)
        relocated = self._record_at_location(record, path)
        overrides = dict(self._location_overrides)
        overrides[model_id] = str(relocated.local_path)
        self._write_location_overrides(overrides)
        self._location_overrides = overrides
        self._location_errors.pop(model_id, None)
        self._models[model_id] = relocated
        return relocated

    def reset_model_location(self, model_id: str) -> ModelRecord:
        record = self.require(model_id)
        default_local, default_runtime = self._default_paths[model_id]
        restored = ModelRecord(dict(record.data), default_local, default_runtime)
        overrides = dict(self._location_overrides)
        overrides.pop(model_id, None)
        self._write_location_overrides(overrides)
        self._location_overrides = overrides
        self._location_errors.pop(model_id, None)
        self._models[model_id] = restored
        return restored

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

    def public_models(
        self,
        *,
        active_model_id: str | None = None,
        include_paths: bool = False,
    ) -> list[dict[str, Any]]:
        result = super().public_models(active_model_id=active_model_id)
        by_id = {record.id: record for record in self.records()}
        for item in result:
            record = by_id[item["id"]]
            item["host_platform"] = self.platform_name
            item["platform_support"] = record.data.get(
                "platform_support",
                "validated-project-path" if self.platform_name == "linux" else "unknown",
            )
            item["location_source"] = (
                "external" if record.id in self._location_overrides else "default"
            )
            item["location_configured"] = record.id in self._location_overrides
            item["location_available"] = record.local_path.exists()
            item["location_error"] = self._location_errors.get(record.id)
            item["path_visible"] = bool(include_paths)
            if include_paths:
                default_local, _default_runtime = self._default_paths[record.id]
                item["model_path"] = str(record.local_path)
                item["runtime_path"] = str(record.runtime_path)
                item["default_model_path"] = str(default_local)
        return result


__all__ = ["ModelRecord", "ModelRegistry", "ModelRegistryError"]
