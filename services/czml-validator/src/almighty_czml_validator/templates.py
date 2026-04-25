"""CZML template loader. Reads from the repo's `czml/templates/` directory by default."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[4]
TEMPLATES_DIR_DEFAULT = REPO_ROOT_DEFAULT / "czml" / "templates"


class TemplateNotFound(LookupError):
    pass


class TemplateLoader:
    def __init__(self, templates_dir: Path | str | None = None) -> None:
        self.templates_dir = Path(templates_dir) if templates_dir else TEMPLATES_DIR_DEFAULT
        self._cache: dict[tuple[str, int], dict[str, Any]] = {}

    def load(self, template_id: str, version: int = 1) -> dict[str, Any]:
        key = (template_id, version)
        if key in self._cache:
            return self._cache[key]
        path = self.templates_dir / f"{template_id}.czml.json"
        if not path.is_file():
            raise TemplateNotFound(f"template '{template_id}' not found at {path}")
        with path.open() as f:
            template = json.load(f)
        if template.get("version") != version:
            raise TemplateNotFound(
                f"template '{template_id}' on disk is version {template.get('version')}, "
                f"requested {version}"
            )
        self._cache[key] = template
        return template
