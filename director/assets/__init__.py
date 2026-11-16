"""Dynamic single-skill asset/scene adapter loader.

Imports ONLY the locked `selected_skill` adapter module so zero code from the other
five skill adapters is ever loaded or executed during a run.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Dict, List

from .. import VALID_SKILLS
from ..provenance_guard import StyleLockViolationError


def build_locked_engine_workspace(
    selected_skill: str,
    project_root: Path,
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
) -> Dict[str, Any]:
    """Dynamically load ONLY `<selected_skill>_adapter` and materialize `<run_dir>/engine_work/`."""
    if selected_skill not in VALID_SKILLS:
        raise StyleLockViolationError(f"Refusing to load unknown skill adapter: {selected_skill}")

    mod_slug = selected_skill.replace("-", "_") + "_adapter"
    mod = importlib.import_module(f"director.assets.{mod_slug}")
    result: Dict[str, Any] = mod.generate_engine_project(
        project_root=project_root,
        run_dir=run_dir,
        storyboard=storyboard,
        parsed_script=parsed_script,
    )

    # Verify visual_sources contain zero foreign skill paths before returning
    visual_sources: List[str] = result.get("visual_sources", [])
    for src in visual_sources:
        for other in VALID_SKILLS:
            if other != selected_skill and (f"skills/{other}" in src or f"{other.replace('-', '_')}_adapter" in src):
                raise StyleLockViolationError(
                    f"Adapter '{selected_skill}' referenced foreign source '{src}'"
                )
    return result
