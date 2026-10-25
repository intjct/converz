"""User settings, saved as JSON in %APPDATA%\\Converz\\settings.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from . import APP_NAME


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    d = os.path.join(base, APP_NAME)
    os.makedirs(d, exist_ok=True)
    return d


@dataclass
class Settings:
    trigger_key: str = "ctrl"          # ctrl / shift / alt
    enabled: bool = True               # hold-key-and-drag watcher on/off
    quality: str = "balanced"          # small / balanced / best
    output_mode: str = "same"          # same (next to original) / folder
    output_folder: str = ""
    start_with_windows: bool = True
    send_to_menu: bool = True
    first_run_done: bool = False
    usage: dict = field(default_factory=dict)

    @property
    def out_dir(self) -> str | None:
        if self.output_mode == "folder" and self.output_folder:
            return self.output_folder
        return None

    @classmethod
    def load(cls) -> "Settings":
        try:
            with open(os.path.join(config_dir(), "settings.json"), encoding="utf-8") as f:
                data = json.load(f)
            known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
            s = cls(**known)
        except Exception:
            s = cls()
        if s.trigger_key not in ("ctrl", "shift", "alt"):
            s.trigger_key = "ctrl"
        if s.quality not in ("small", "balanced", "best"):
            s.quality = "balanced"
        return s

    def save(self) -> None:
        path = os.path.join(config_dir(), "settings.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def count_use(self, action_id: str) -> None:
        self.usage[action_id] = self.usage.get(action_id, 0) + 1
