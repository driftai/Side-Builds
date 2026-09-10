from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_settings() -> dict:
    settings_path = ROOT / "config" / "settings.json"
    with open(settings_path, "r", encoding="utf-8") as fp:
        settings = json.load(fp)

    # Context profiles can provide their measured normal MoE residency so the
    # coexistence manager restores the correct cache geometry for 12K vs 8K.
    profile_slots = os.environ.get("LOCAL_MOE_NORMAL_MOE_SLOTS")
    if profile_slots:
        try:
            settings["gpu_coexistence_normal_moe_slots"] = max(1, int(profile_slots))
        except ValueError:
            pass

    # Resolve model_root relative to project root if not absolute
    model_root = Path(settings.get("model_root", "models"))
    if not model_root.is_absolute():
        settings["model_root"] = str((ROOT / model_root).resolve())

    return settings
