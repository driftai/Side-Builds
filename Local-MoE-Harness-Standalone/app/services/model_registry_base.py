from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ModelRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class ModelRecord:
    data: dict[str, Any]
    local_path: Path
    runtime_path: Path

    @property
    def id(self) -> str:
        return str(self.data["id"])

    @property
    def served_model_name(self) -> str:
        return str(self.data["served_model_name"])

    @property
    def selectable(self) -> bool:
        return bool(self.data.get("selectable"))


class ModelRegistry:
    """Trusted model catalog plus ignored, machine-local selection state."""

    def __init__(
        self,
        root: Path,
        *,
        registry_path: Path | None = None,
        state_path: Path | None = None,
    ) -> None:
        self.root = root.resolve()
        self.registry_path = registry_path or self.root / "config" / "models.json"
        self.state_path = state_path or self.root / "state" / "selected-model.json"
        self._document = self._load_document()
        self.disk_reserve_gb = float(self._document.get("disk_reserve_gb", 30))
        self._models = self._parse_models(self._document.get("models"))
        self.default_model_id = str(self._document.get("default_model_id") or "")
        default = self._models.get(self.default_model_id)
        if default is None or not default.selectable:
            raise ModelRegistryError("default_model_id must name a selectable registry model")

    def _load_document(self) -> dict[str, Any]:
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"Model registry is unreadable: {exc}") from exc
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ModelRegistryError("Model registry schema_version must be 1")
        return data

    def _parse_models(self, raw_models: object) -> dict[str, ModelRecord]:
        if not isinstance(raw_models, list) or not raw_models:
            raise ModelRegistryError("Model registry must contain a non-empty models list")
        records: dict[str, ModelRecord] = {}
        for index, raw in enumerate(raw_models):
            if not isinstance(raw, dict):
                raise ModelRegistryError(f"models[{index}] must be an object")
            model_id = raw.get("id")
            if not isinstance(model_id, str) or not model_id or model_id in records:
                raise ModelRegistryError(f"models[{index}].id is missing or duplicated")
            local_value = raw.get("local_path")
            if not isinstance(local_value, str) or not local_value:
                raise ModelRegistryError(f"{model_id}: local_path must be a relative path")
            relative = Path(local_value)
            if relative.is_absolute() or ".." in relative.parts:
                raise ModelRegistryError(f"{model_id}: local_path must stay inside the project")
            local_path = (self.root / relative).resolve()
            try:
                local_path.relative_to((self.root / "models").resolve())
            except ValueError as exc:
                raise ModelRegistryError(f"{model_id}: local_path must stay under models/") from exc
            required = raw.get("required_files")
            if not isinstance(required, list) or not required:
                raise ModelRegistryError(f"{model_id}: required_files must be non-empty")
            for filename in required:
                if (
                    not isinstance(filename, str)
                    or "\\" in filename
                    or Path(filename).is_absolute()
                    or ".." in Path(filename).parts
                ):
                    raise ModelRegistryError(f"{model_id}: unsafe required file {filename!r}")
            serve_value = raw.get("serve_file")
            runtime_path = local_path
            if serve_value is not None:
                serve_relative = Path(str(serve_value))
                if (
                    not isinstance(serve_value, str)
                    or not serve_value
                    or "\\" in serve_value
                    or serve_relative.is_absolute()
                    or ".." in serve_relative.parts
                    or serve_relative == Path(".")
                ):
                    raise ModelRegistryError(
                        f"{model_id}: serve_file must be a safe relative path"
                    )
                if serve_value not in required:
                    raise ModelRegistryError(
                        f"{model_id}: serve_file must be included in required_files"
                    )
                runtime_path = (local_path / serve_relative).resolve()
                try:
                    runtime_path.relative_to(local_path)
                except ValueError as exc:
                    raise ModelRegistryError(
                        f"{model_id}: serve_file must stay inside the model directory"
                    ) from exc
            if raw.get("selectable"):
                self._validate_profiles(model_id, raw.get("profiles"))
            self._validate_download(model_id, raw.get("download"), required)
            records[model_id] = ModelRecord(dict(raw), local_path, runtime_path)
        return records

    @staticmethod
    def _validate_download(
        model_id: str, download: object, required_files: list[object]
    ) -> None:
        if download is None:
            return
        if not isinstance(download, dict):
            raise ModelRegistryError(f"{model_id}: download must be an object or null")
        files = download.get("files")
        expected_bytes = download.get("expected_bytes")
        if not isinstance(expected_bytes, int) or expected_bytes <= 0:
            raise ModelRegistryError(f"{model_id}: invalid expected download size")
        if not isinstance(files, list) or not files:
            raise ModelRegistryError(f"{model_id}: download files must be non-empty")
        for filename in files:
            path = Path(str(filename))
            if (
                not isinstance(filename, str)
                or path.is_absolute()
                or ".." in path.parts
            ):
                raise ModelRegistryError(
                    f"{model_id}: unsafe download file {filename!r}"
                )
        if not set(required_files).issubset(files):
            raise ModelRegistryError(
                f"{model_id}: required files must be included in download files"
            )

    @staticmethod
    def _validate_profiles(model_id: str, profiles: object) -> None:
        if not isinstance(profiles, dict):
            raise ModelRegistryError(f"{model_id}: selectable models require profiles")
        required_profiles = {"normal", "busy", "recovery"}
        if set(profiles) != required_profiles:
            raise ModelRegistryError(f"{model_id}: profiles must be normal, busy, and recovery")
        required_fields = {
            "label", "kv_tokens", "prefill_tokens", "d2d", "memory_ratio",
            "graph", "moe_slots", "startup_timeout", "request_timeout",
        }
        for name, profile in profiles.items():
            if not isinstance(profile, dict) or set(profile) != required_fields:
                raise ModelRegistryError(f"{model_id}: invalid {name} profile fields")
            if int(profile["kv_tokens"]) < 512 or int(profile["prefill_tokens"]) < 128:
                raise ModelRegistryError(f"{model_id}: unsafe {name} token geometry")

    def records(self) -> tuple[ModelRecord, ...]:
        return tuple(self._models.values())

    def require(self, model_id: str) -> ModelRecord:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise ModelRegistryError(f"Unknown model id: {model_id}") from exc

    def is_installed(self, record_or_id: ModelRecord | str) -> bool:
        record = record_or_id if isinstance(record_or_id, ModelRecord) else self.require(record_or_id)
        for filename in record.data["required_files"]:
            path = record.local_path / filename
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(record.local_path)
                if not resolved.is_file() or resolved.stat().st_size <= 0:
                    return False
            except (OSError, ValueError):
                return False
        if record.runtime_path != record.local_path:
            try:
                runtime_path = record.runtime_path.resolve(strict=True)
                runtime_path.relative_to(record.local_path)
                if not runtime_path.is_file():
                    return False
            except (OSError, ValueError):
                return False
        return True

    def require_selectable_installed(self, model_id: str) -> ModelRecord:
        record = self.require(model_id)
        if not record.selectable:
            raise ModelRegistryError(f"Model is not selectable on this machine: {model_id}")
        if not self.is_installed(record):
            raise ModelRegistryError(f"Model is not installed: {model_id}")
        return record

    def profile(self, model_id: str, profile_name: str) -> dict[str, Any]:
        record = self.require(model_id)
        try:
            return dict(record.data["profiles"][profile_name])
        except KeyError as exc:
            raise ModelRegistryError(f"{model_id} has no {profile_name} profile") from exc

    def selected_model_id(self) -> str:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            candidate = str(data.get("model_id") or "")
            self.require_selectable_installed(candidate)
            return candidate
        except (OSError, json.JSONDecodeError, ModelRegistryError):
            return self.default_model_id

    def persist_selection(self, model_id: str) -> None:
        self.require_selectable_installed(model_id)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"model_id": model_id, "selected_at": int(time.time())},
            indent=2,
        ) + "\n"
        fd, temp_name = tempfile.mkstemp(
            prefix="selected-model.", suffix=".tmp", dir=self.state_path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def public_models(self, *, active_model_id: str | None = None) -> list[dict[str, Any]]:
        selected = self.selected_model_id()
        result = []
        for record in self.records():
            installed = self.is_installed(record)
            download = record.data.get("download") or {}
            if record.data.get("validation") == "not_viable":
                availability = "not_viable"
            elif installed:
                availability = "installed"
            elif download:
                availability = "available"
            else:
                availability = "not_tested"
            result.append(
                {
                    "id": record.id,
                    "display_name": record.data["display_name"],
                    "hf_repo": record.data["hf_repo"],
                    "architecture": record.data["architecture"],
                    "kind": record.data["kind"],
                    "quantization": record.data["quantization"],
                    "validation": record.data["validation"],
                    "selectable": record.selectable,
                    "installed": installed,
                    "availability": availability,
                    "selected": record.id == selected,
                    "active": record.id == active_model_id,
                    "download_supported": bool(download),
                    "expected_download_gb": (
                        round(float(download.get("expected_bytes", 0)) / 1e9, 2)
                        if download
                        else None
                    ),
                    "notes": record.data.get("notes"),
                }
            )
        return result
