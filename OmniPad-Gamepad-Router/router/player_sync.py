"""Validation for settings intentionally shared by browsers on one player slot."""

from __future__ import annotations

from typing import Any, Dict, Mapping


KEYBOARD_TYPES = {"standard", "compact65", "arrowless", "arrow_numpad", "esdf", "vim_camera"}
TOUCH_LAYOUTS = {
    "classic_landscape", "twin_stick_landscape", "playstation_landscape",
    "compact_thumbs", "phone_reach", "camera_actions",
}
HYBRID_PRESETS = {
    "keyboard_touch_camera", "keyboard_mouse_camera", "keyboard_actions",
    "phone_split", "landscape_companion", "full_hybrid", "custom",
}
HYBRID_PARTS = {
    "keyboard", "mouse", "left-stick", "right-stick", "dpad", "actions",
    "shoulders", "center",
}
KEYBOARD_VIEWS = {"standard", "full-fit", "essential"}


def sanitize_shared_config(patch: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Return only recognized, bounded, JSON-safe shared controller settings."""
    source = patch if isinstance(patch, Mapping) else {}
    result: Dict[str, Any] = {}

    if "mouse_sensitivity" in source:
        try:
            result["mouse_sensitivity"] = max(1, min(200, int(source["mouse_sensitivity"])))
        except (TypeError, ValueError):
            pass
    for key in ("mouse_invert_x", "mouse_invert_y"):
        if key in source and isinstance(source[key], bool):
            result[key] = source[key]
    if source.get("touch_layout") in TOUCH_LAYOUTS:
        result["touch_layout"] = source["touch_layout"]
    if source.get("keyboard_type") in KEYBOARD_TYPES:
        result["keyboard_type"] = source["keyboard_type"]
    if source.get("hybrid_preset") in HYBRID_PRESETS:
        result["hybrid_preset"] = source["hybrid_preset"]
    if source.get("hybrid_keyboard_view") in KEYBOARD_VIEWS:
        result["hybrid_keyboard_view"] = source["hybrid_keyboard_view"]
    if "hybrid_parts" in source and isinstance(source["hybrid_parts"], list):
        result["hybrid_parts"] = sorted({str(part) for part in source["hybrid_parts"] if str(part) in HYBRID_PARTS})
    return result
