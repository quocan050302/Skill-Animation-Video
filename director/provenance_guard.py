"""Runtime filesystem, module import, and subprocess provenance guard.

Enforces the Non-Negotiable Single-Skill Rule at the Python interpreter level using
`sys.addaudithook`. In `explicit` mode, touching any file or adapter belonging to the
other five skills raises `StyleLockViolationError` immediately (fail-closed).
In `auto` mode, only `skills/<candidate>/SKILL.md` capability descriptions may be read
before `lock_to_skill()` permanently locks the run to a single engine.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from . import VALID_SKILLS


class StyleLockViolationError(RuntimeError):
    """Raised immediately when code attempts to read, import, or execute a foreign skill."""


def _adapter_slug(skill_name: str) -> str:
    return skill_name.replace("-", "_") + "_adapter"


def _skill_for_adapter_stem(stem: str) -> Optional[str]:
    for s in VALID_SKILLS:
        if stem == s.replace("-", "_") + "_adapter":
            return s
    return None


class ProvenanceGuard:
    """Singleton-capable interpreter audit guard for a Short Director process."""

    _hook_installed = False
    _active_instance: Optional["ProvenanceGuard"] = None
    _lock = threading.RLock()

    def __init__(self, project_root: Path):
        self.project_root = project_root.resolve()
        self.upstream_root = (self.project_root / "vendor" / "claude-animation-skills").resolve()
        self.upstream_skills_root = (self.upstream_root / "skills").resolve()
        self.director_assets_root = (self.project_root / "director" / "assets").resolve()

        self.selection_mode: Optional[str] = None  # "explicit" | "auto"
        self.phase: str = "uninitialized"  # "uninitialized" | "auto_capability_scan" | "locked"
        self.selected_skill: Optional[str] = None
        self.enabled: bool = True

        self.events: List[Dict[str, Any]] = []
        self.violations: List[Dict[str, Any]] = []
        self.opened_skill_files: Set[str] = set()
        self.opened_kit_files: Set[str] = set()
        self.opened_adapter_files: Set[str] = set()
        self.imported_modules: Set[str] = set()
        self.subprocesses: List[List[str]] = []

    @classmethod
    def activate(
        cls,
        project_root: Path,
        selection_mode: str,
        selected_skill: Optional[str] = None,
    ) -> "ProvenanceGuard":
        with cls._lock:
            # Clear cached skill adapters so subsequent imports always pass through the active lock check
            for mod_name in list(sys.modules):
                if mod_name.startswith("director.assets.") and _skill_for_adapter_stem(mod_name.rsplit(".", 1)[-1]) is not None:
                    sys.modules.pop(mod_name, None)
            guard = cls(project_root)
            if selection_mode == "explicit":
                if selected_skill not in VALID_SKILLS:
                    raise StyleLockViolationError(
                        f"Invalid explicit skill '{selected_skill}'. Valid skills: {', '.join(VALID_SKILLS)}"
                    )
                guard.selection_mode = "explicit"
                guard.selected_skill = selected_skill
                guard.phase = "locked"
            elif selection_mode == "auto":
                guard.selection_mode = "auto"
                guard.phase = "auto_capability_scan"
                if selected_skill is not None:
                    guard.lock_to_skill(selected_skill)
            else:
                raise ValueError(f"Unsupported selection_mode: {selection_mode}")

            cls._active_instance = guard
            if not cls._hook_installed:
                sys.addaudithook(cls._audit_dispatch)
                cls._hook_installed = True
            return guard

    @classmethod
    def current(cls) -> Optional["ProvenanceGuard"]:
        return cls._active_instance

    @classmethod
    def deactivate(cls) -> None:
        with cls._lock:
            if cls._active_instance is not None:
                cls._active_instance.enabled = False
            cls._active_instance = None

    def lock_to_skill(self, skill_name: str) -> None:
        with self._lock:
            if skill_name not in VALID_SKILLS:
                raise StyleLockViolationError(
                    f"Cannot lock to invalid skill '{skill_name}'. Valid skills: {', '.join(VALID_SKILLS)}"
                )
            if self.phase == "locked" and self.selected_skill and self.selected_skill != skill_name:
                self._record_violation(
                    "re_lock_attempt",
                    f"Attempted to switch locked skill from '{self.selected_skill}' to '{skill_name}'",
                )
                raise StyleLockViolationError(
                    f"Style lock is immutable: cannot switch '{self.selected_skill}' -> '{skill_name}'"
                )
            self.selected_skill = skill_name
            self.phase = "locked"
            self.events.append(
                {
                    "ts": round(time.time(), 4),
                    "event": "lock_engaged",
                    "selection_mode": self.selection_mode,
                    "selected_skill": skill_name,
                }
            )

    def _record_violation(self, kind: str, detail: str, path: Optional[str] = None) -> None:
        entry = {
            "ts": round(time.time(), 4),
            "kind": kind,
            "detail": detail,
            "path": path,
            "selected_skill": self.selected_skill,
            "selection_mode": self.selection_mode,
            "phase": self.phase,
        }
        self.violations.append(entry)

    def _check_resolved_path(self, raw_path: Any, op: str) -> None:
        if not isinstance(raw_path, (str, bytes, os.PathLike)):
            return
        try:
            p_str = os.fsdecode(raw_path)
            p_low = p_str.replace("\\", "/").lower()
            root_low = str(self.project_root).replace("\\", "/").lower()
            # Fast-path ignore system paths outside project_root
            if root_low not in p_low and "short-director" not in p_low and "claude-animation-skills" not in p_low and not p_str.startswith("."):
                return
            resolved = Path(p_str).resolve()
        except Exception:
            return

        res_str = str(resolved)
        res_cmp = os.path.normcase(res_str)
        skills_prefix = os.path.normcase(str(self.upstream_skills_root) + os.sep)
        kit_prefix = os.path.normcase(str((self.upstream_root / "kit").resolve()) + os.sep)
        assets_prefix = os.path.normcase(str(self.director_assets_root) + os.sep)

        if res_cmp.startswith(skills_prefix):
            rel = res_str[len(skills_prefix) :]
            parts = rel.split(os.sep)
            target_skill = parts[0] if parts else ""
            rel_inside = "/".join(parts[1:])

            if self.phase == "auto_capability_scan":
                # Auto planning may ONLY read SKILL.md capability descriptions, never engine/build/template!
                if rel_inside != "SKILL.md":
                    msg = (
                        f"Auto-selection phase tried to access engine/template file '{rel}' "
                        f"via {op} before locking one skill."
                    )
                    self._record_violation("auto_scan_engine_leak", msg, res_str)
                    raise StyleLockViolationError(msg)
                self.events.append(
                    {"ts": round(time.time(), 4), "event": "capability_read", "skill": target_skill, "path": res_str}
                )
                return

            if self.phase == "locked":
                if target_skill != self.selected_skill:
                    msg = (
                        f"FORBIDDEN foreign skill access via {op}: '{target_skill}' "
                        f"(locked to '{self.selected_skill}'): {res_str}"
                    )
                    self._record_violation("foreign_skill_file_access", msg, res_str)
                    raise StyleLockViolationError(msg)
                self.opened_skill_files.add(res_str)

        elif res_cmp.startswith(kit_prefix):
            self.opened_kit_files.add(res_str)

        elif res_cmp.startswith(assets_prefix):
            stem = resolved.stem
            owner_skill = _skill_for_adapter_stem(stem)
            if owner_skill is not None:
                if self.phase != "locked" or owner_skill != self.selected_skill:
                    msg = (
                        f"FORBIDDEN foreign adapter access via {op}: '{stem}' belongs to '{owner_skill}' "
                        f"(locked to '{self.selected_skill}')"
                    )
                    self._record_violation("foreign_adapter_access", msg, res_str)
                    raise StyleLockViolationError(msg)
                self.opened_adapter_files.add(res_str)

    def verify_adapter_allowed(self, adapter_stem: str) -> None:
        """Explicitly verify that importing/loading a visual adapter respects the active lock."""
        owner = _skill_for_adapter_stem(adapter_stem)
        if owner is not None and (self.phase != "locked" or owner != self.selected_skill):
            msg = (
                f"FORBIDDEN foreign adapter load '{adapter_stem}' "
                f"(locked to '{self.selected_skill}')"
            )
            self._record_violation("foreign_adapter_import", msg, adapter_stem)
            raise StyleLockViolationError(msg)

    def _handle_event(self, event: str, args: Any) -> None:
        if not self.enabled:
            return
        if event == "open":
            if args:
                self._check_resolved_path(args[0], "open")
        elif event in ("os.listdir", "os.scandir"):
            if args and args[0] is not None:
                self._check_resolved_path(args[0], event)
        elif event == "import":
            mod_name = args[0] if args else ""
            if isinstance(mod_name, str) and "director.assets." in mod_name:
                leaf = mod_name.rsplit(".", 1)[-1]
                owner = _skill_for_adapter_stem(leaf)
                if owner is not None:
                    if self.phase != "locked" or owner != self.selected_skill:
                        msg = (
                            f"FORBIDDEN foreign adapter import '{mod_name}' "
                            f"(locked to '{self.selected_skill}')"
                        )
                        self._record_violation("foreign_adapter_import", msg, mod_name)
                        raise StyleLockViolationError(msg)
                    self.imported_modules.add(mod_name)
        elif event == "subprocess.Popen":
            # args = (executable, args_list, cwd, env)
            cmd_args = args[1] if len(args) > 1 and isinstance(args[1], (list, tuple)) else []
            str_cmd = [str(x) for x in cmd_args]
            for token in str_cmd:
                if "install.sh" in token and "claude-animation-skills" in token:
                    msg = f"FORBIDDEN invocation of Claude Code-only upstream install.sh: {str_cmd}"
                    self._record_violation("forbidden_claude_installer", msg, token)
                    raise StyleLockViolationError(msg)
                for s in VALID_SKILLS:
                    if self.phase == "locked" and s != self.selected_skill:
                        if f"skills/{s}" in token or f"skills\\{s}" in token or _skill_for_adapter_stem(Path(token).stem) == s:
                            msg = (
                                f"FORBIDDEN subprocess argument referencing foreign skill '{s}' "
                                f"(locked to '{self.selected_skill}'): {token}"
                            )
                            self._record_violation("foreign_subprocess_arg", msg, token)
                            raise StyleLockViolationError(msg)
            with self._lock:
                if len(self.subprocesses) < 500:
                    self.subprocesses.append(str_cmd)

    @classmethod
    def _audit_dispatch(cls, event: str, args: Any) -> None:
        inst = cls._active_instance
        if inst is not None and inst.enabled:
            inst._handle_event(event, args)

    def snapshot_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "guard_active": self.enabled,
                "selection_mode": self.selection_mode,
                "phase": self.phase,
                "selected_skill": self.selected_skill,
                "opened_skill_files": sorted(self.opened_skill_files),
                "opened_kit_files": sorted(self.opened_kit_files),
                "opened_adapter_files": sorted(self.opened_adapter_files),
                "imported_adapter_modules": sorted(self.imported_modules),
                "subprocess_count": len(self.subprocesses),
                "subprocesses": self.subprocesses,
                "events": list(self.events),
                "violations": list(self.violations),
            }
