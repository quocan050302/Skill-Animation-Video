"""Dynamic single-skill asset/scene adapter loader.

Imports ONLY the locked `selected_skill` adapter module so zero code from the other
five skill adapters is ever loaded or executed during a run.
"""

from __future__ import annotations

import importlib
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from .. import VALID_SKILLS
from ..provenance_guard import ProvenanceGuard, StyleLockViolationError


def link_kit_node_modules(src_node_modules: Path, dst_node_modules: Path) -> str:
    """Link shared `kit/node_modules` into `engine_work` (symlink, or Windows directory junction)."""
    src = str(src_node_modules.resolve())
    dst = str(dst_node_modules)
    try:
        os.symlink(src, dst, target_is_directory=True)
        return "symlink"
    except OSError:
        if os.name == "nt":
            try:
                import _winapi  # type: ignore[attr-defined]
                _winapi.CreateJunction(src, dst)
                return "junction"
            except Exception:
                subprocess.run(["cmd", "/c", "mklink", "/J", dst, src], check=True, capture_output=True)
                return "junction"
        raise


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
    guard = ProvenanceGuard.current()
    if guard is not None:
        guard.verify_adapter_allowed(mod_slug)
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
