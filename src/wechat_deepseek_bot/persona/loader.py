"""Load editable JSON persona files without coupling them to the engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class PersonaLoadError(ValueError):
    pass


def load_personas(directory: Path) -> Dict[str, Dict[str, Any]]:
    personas: Dict[str, Dict[str, Any]] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PersonaLoadError(f"cannot load persona {path.name}") from exc
        name = str(value.get("name", path.stem)).strip()
        if not name:
            raise PersonaLoadError(f"persona {path.name} has no name")
        personas[name] = value
    if not personas:
        raise PersonaLoadError(f"no persona files found in {directory}")
    return personas
