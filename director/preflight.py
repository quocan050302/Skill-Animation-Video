"""STEP 0: Platform, toolchain, WebGL GPU, voice coverage, and disk-quota preflight."""

from __future__ import annotations

import glob
import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .audio_catalog import (
    AudioAsset,
    LicensePolicy,
    ValidationResult,
    discover_native_audio_assets,
    discover_qa_audio_assets,
    discover_user_music_asset,
    validate_audio_asset,
)


KOKORO_VERIFIED_LANGS = {
    "en": "en-us",
    "en-us": "en-us",
    "en-gb": "en-gb",
    "fr": "fr-fr",
    "es": "es",
    "it": "it",
    "pt": "pt-br",
    "ja": "ja",
    "ko": "ko",
    "zh": "cmn",
    "hi": "hi",
    # NOTE: Vietnamese ('vi', 'vi-vn') is explicitly NOT supported by Kokoro v1.0.
}


@dataclass
class PreflightResult:
    ok: bool
    os_name: str
    arch: str
    cpu_count: int
    recommended_workers: int
    disk_total_gb: float
    disk_free_gb: float
    disk_quota_min_gb: float
    ffmpeg_path: Optional[str]
    ffprobe_path: Optional[str]
    node_path: Optional[str]
    browser_executable: Optional[str]
    webgl_backend: str  # "metal" | "angle-gl" | "swiftshader" | "unavailable"
    kit_ready: bool
    upstream_sha: str
    upstream_clean: bool
    voice_backends: Dict[str, Any]
    native_4k_capabilities: Dict[str, Any]
    notes: List[str]
    errors: List[str]
    qa_audio_root: Optional[str] = None
    qa_audio_status: str = "QA_LIBRARY_UNAVAILABLE"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_qa_audio_root(
    project_root: Path,
    cli_qa_root: Optional[Path] = None,
) -> Tuple[Optional[Path], str, str]:
    """Locate optional read-only QA-Unified-Video-Studio root cleanly without unbounded HOME scans.

    Priority order:
      1. CLI `--qa-audio-root`
      2. Env `SHORT_DIRECTOR_QA_ROOT`
      3. Local config `<project_root>/.short_director_local.json` (`qa_audio_root`)
      4. Trusted workspace sibling `<project_root.parent>/QA-Unified-Video-Studio`
    """
    candidates: List[Tuple[str, Path]] = []
    if cli_qa_root is not None:
        candidates.append(("cli_flag", cli_qa_root))
    env_root = os.environ.get("SHORT_DIRECTOR_QA_ROOT")
    if env_root:
        candidates.append(("env:SHORT_DIRECTOR_QA_ROOT", Path(env_root)))
    local_cfg = project_root / ".short_director_local.json"
    if local_cfg.exists():
        try:
            cfg = json.loads(local_cfg.read_text(encoding="utf-8"))
            if isinstance(cfg, dict) and cfg.get("qa_audio_root"):
                candidates.append(("local_config", Path(str(cfg["qa_audio_root"]))))
        except Exception:
            pass
    sibling = project_root.parent / "QA-Unified-Video-Studio"
    candidates.append(("workspace_sibling", sibling))

    for origin, cand in candidates:
        try:
            res = cand.resolve(strict=False)
        except Exception:
            continue
        if res.exists() and res.is_dir() and (res / "audio").is_dir():
            return res, "QA_LIBRARY_MOUNTED_READONLY", f"Resolved QA audio library ({origin}): {res}"

    if cli_qa_root is not None:
        return None, "QA_LIBRARY_UNAVAILABLE", f"Explicit --qa-audio-root missing or has no audio/: {cli_qa_root}"
    return None, "QA_LIBRARY_UNAVAILABLE", "QA audio library not present locally; native procedural audio engine active."


def preflight_audio_assets(
    project_root: Path,
    qa_audio_root: Optional[Path],
    qa_status: str,
    music_mode: str = "auto",
    sfx_mode: str = "auto",
    music_file: Optional[Path] = None,
    music_rights_confirmed: bool = False,
    disk_free_gb: float = 10.0,
    prepare_qa_audio_library: bool = False,
) -> Dict[str, Any]:
    """Fail-closed preflight of audio sources BEFORE launching costly 4K scene rendering."""
    errors: List[str] = []
    warnings: List[str] = []

    estimated_audio_disk_mb = 45.0
    if disk_free_gb * 1024.0 < estimated_audio_disk_mb * 2:
        errors.append(f"Insufficient disk space for 48 kHz audio stems ({disk_free_gb:.2f} GiB free)")

    # Explicit opt-in only for optional QA library build helper (never auto-triggered by missing files!)
    if prepare_qa_audio_library:
        if not qa_audio_root or not (qa_audio_root / "audio" / "build_audio.py").exists():
            errors.append("--prepare-qa-audio-library requested, but QA audio/build_audio.py not found under resolved root.")
        elif disk_free_gb < 5.0:
            errors.append(f"Refusing --prepare-qa-audio-library under tight disk quota ({disk_free_gb:.2f} GiB < 5.0 GiB)")
        else:
            warnings.append("Explicit --prepare-qa-audio-library opt-in acknowledged (checking existing assets read-only first).")

    native_catalog = discover_native_audio_assets(project_root)
    qa_catalog = discover_qa_audio_assets(qa_audio_root) if (qa_audio_root and qa_status == "QA_LIBRARY_MOUNTED_READONLY") else []
    catalog: List[AudioAsset] = native_catalog + qa_catalog

    policy = LicensePolicy(allow_user_file_without_sidecar=music_rights_confirmed)
    validations: Dict[str, ValidationResult] = {}
    allowed_roots: List[Path] = []
    if qa_audio_root and qa_audio_root.exists():
        allowed_roots.append(qa_audio_root.resolve())
    if music_file and music_file.exists():
        allowed_roots.append(music_file.resolve().parent)

    verified_qa_music: List[str] = []
    verified_qa_sfx: List[str] = []
    rejected_qa: List[Dict[str, str]] = []

    for item in qa_catalog:
        v = validate_audio_asset(item, policy, allowed_roots=allowed_roots or None)
        validations[item.asset_id] = v
        if v.ok:
            if item.asset_type == "music":
                verified_qa_music.append(item.asset_id)
            elif item.asset_type == "sfx":
                verified_qa_sfx.append(item.asset_id)
        else:
            rejected_qa.append({"asset_id": item.asset_id, "reason": v.reason})

    if music_mode == "qa-library" and not verified_qa_music:
        errors.append(
            "Requested --music-mode qa-library failed preflight: no verified QA music beds available "
            f"(qa_status={qa_status}, rejected={len(rejected_qa)}). Supply valid --qa-audio-root or switch to --music-mode auto."
        )
    if sfx_mode == "qa-library" and not verified_qa_sfx:
        errors.append(
            "Requested --sfx-mode qa-library failed preflight: no verified QA SFX assets available "
            f"(qa_status={qa_status}, rejected={len(rejected_qa)})."
        )

    if music_mode == "file":
        if music_file is None:
            errors.append("--music-mode file requires --music-file <absolute-path>.")
        else:
            um = discover_user_music_asset(music_file, rights_confirmed=music_rights_confirmed)
            v_u = validate_audio_asset(um, policy, allowed_roots=[music_file.resolve().parent])
            validations[um.asset_id] = v_u
            if not v_u.ok:
                errors.append(f"--music-file preflight rejected: {v_u.reason}")

    if qa_status == "QA_LIBRARY_UNAVAILABLE" and (music_mode == "auto" or sfx_mode == "auto"):
        warnings.append("QA_LIBRARY_UNAVAILABLE: Standalone native procedural synthesis will be used cleanly.")
    if rejected_qa:
        warnings.append(f"Skipped {len(rejected_qa)} unverified/corrupt external QA asset(s) during preflight.")

    return {
        "ok": len(errors) == 0,
        "qa_audio_root": str(qa_audio_root.resolve()) if qa_audio_root else None,
        "qa_audio_status": qa_status,
        "native_assets_count": len(native_catalog),
        "qa_assets_discovered": len(qa_catalog),
        "verified_qa_music_count": len(verified_qa_music),
        "verified_qa_sfx_count": len(verified_qa_sfx),
        "rejected_qa_assets": rejected_qa,
        "catalog": catalog,
        "estimated_audio_disk_mb": estimated_audio_disk_mb,
        "warnings": warnings,
        "errors": errors,
    }


def find_browser_executable() -> Optional[str]:
    env_chrome = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME")
    if env_chrome and os.path.exists(env_chrome):
        return env_chrome

    home = Path.home()
    sys_name = platform.system().lower()
    patterns = [
        str(home / "Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        str(home / "Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
        str(home / ".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
    ]
    if sys_name == "windows":
        local_app = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData/Local")))
        patterns.extend([
            str(local_app / "ms-playwright/chromium-*/chrome-win/chrome.exe"),
            str(home / ".cache/ms-playwright/chromium-*/chrome-win/chrome.exe"),
        ])

    for pat in patterns:
        matches = sorted(glob.glob(pat), reverse=True)
        for m in matches:
            p = Path(m)
            if p.exists() and (sys_name == "windows" or os.access(m, os.X_OK)):
                # Guard against incomplete partial Playwright downloads (0-byte chrome.dll)
                dll = p.parent / "chrome.dll"
                if sys_name == "windows" and dll.exists() and dll.stat().st_size == 0:
                    continue
                return m

    system_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    if sys_name == "windows":
        system_candidates.extend([
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            shutil.which("chrome"),
            shutil.which("msedge"),
        ])
    for c in system_candidates:
        if c and os.path.exists(c) and (sys_name == "windows" or os.access(c, os.X_OK)):
            return c
    return None


def probe_windows_sapi_voices() -> Dict[str, List[str]]:
    """Query Windows System.Speech installed voices when running on Windows."""
    if platform.system().lower() != "windows":
        return {}
    ps_bin = shutil.which("powershell")
    if not ps_bin:
        return {}
    cmd = (
        "$ProgressPreference = 'SilentlyContinue'; "
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.GetInstalledVoices() | ForEach-Object { "
        "Write-Output ($_.VoiceInfo.Name + '|' + $_.VoiceInfo.Culture.Name + '|' + $_.Enabled) }"
    )
    try:
        res = subprocess.run([ps_bin, "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=8, check=True)
    except Exception:
        return {}
    by_lang: Dict[str, List[str]] = {}
    for line in res.stdout.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3 or parts[2].lower() != "true":
            continue
        vname, culture = parts[0], parts[1].replace("_", "-").lower()
        short_lang = culture.split("-")[0]
        by_lang.setdefault(culture, []).append(vname)
        by_lang.setdefault(short_lang, []).append(vname)
    return by_lang


def probe_macos_say_voices() -> Dict[str, List[str]]:
    """Query `say -v '?'` on macOS to verify actually installed voices per language prefix."""
    say_bin = shutil.which("say")
    if not say_bin or platform.system().lower() != "darwin":
        return {}
    try:
        res = subprocess.run([say_bin, "-v", "?"], capture_output=True, text=True, timeout=5, check=True)
    except Exception:
        return {}
    by_lang: Dict[str, List[str]] = {}
    for line in res.stdout.splitlines():
        # Format: "Samantha            en_US    # Hello! My name is Samantha."
        m = re.match(r"^(.+?)\s+([a-z]{2}[_-][A-Z]{2})\s+#", line)
        if not m:
            continue
        voice_name = m.group(1).strip()
        locale = m.group(2).replace("_", "-").lower()
        short_lang = locale.split("-")[0]
        by_lang.setdefault(locale, []).append(voice_name)
        by_lang.setdefault(short_lang, []).append(voice_name)
    return by_lang


def verify_language_voice_support(
    lang: str,
    kit_dir: Path,
    user_voice_file: Optional[Path] = None,
    requested_backend: str = "auto",
    requested_voice_id: Optional[str] = None,
) -> Tuple[bool, str, str, str]:
    """Return (supported, backend, voice_id, explanation) truthfully."""
    norm = lang.strip().lower().replace("_", "-")
    base = norm.split("-")[0]
    req_b = (requested_backend or "auto").lower()
    req_vid = requested_voice_id.strip() if requested_voice_id else None

    if user_voice_file is not None:
        if user_voice_file.exists():
            return (True, "user_file", str(user_voice_file), f"Verified user-supplied audio file ({user_voice_file.name}).")
        return (False, "none", "", f"User voice file does not exist: {user_voice_file}")

    if req_b in ("auto", "kokoro"):
        kokoro_model = kit_dir / "models" / "kokoro-v1.0.onnx"
        kokoro_voices = kit_dir / "models" / "voices-v1.0.bin"
        if kokoro_model.exists() and kokoro_voices.exists():
            if norm in KOKORO_VERIFIED_LANGS or base in KOKORO_VERIFIED_LANGS:
                return (
                    True,
                    "kokoro",
                    "am_michael",
                    f"Kokoro v1.0 ONNX verified for language '{norm}'.",
                )
        if req_b == "kokoro":
            return (
                False,
                "none",
                "",
                f"Requested --voice-backend kokoro unavailable: missing {kokoro_model.name} or unsupported language '{norm}'.",
            )

    if req_b in ("auto", "macos_say"):
        say_voices = probe_macos_say_voices()
        if say_voices:
            candidates = say_voices.get(norm) or say_voices.get(base) or []
            if candidates:
                if req_vid:
                    matched_say = next((c for c in candidates if c.lower() == req_vid.lower()), None)
                    if not matched_say:
                        return (
                            False,
                            "none",
                            "",
                            f"Requested --voice-id '{req_vid}' not found in macOS say voices for '{norm}': {candidates}",
                        )
                    chosen = matched_say
                else:
                    preferred_order = {
                        "en": ["Samantha", "Daniel", "Reed (English (US))", "Eddy (English (US))", "Karen"],
                        "vi": ["Linh"],
                    }.get(base, [])
                    chosen = next((p for p in preferred_order if p in candidates), candidates[0])
                note = f"macOS Speech Synthesis (`say`) verified installed voice '{chosen}' for '{norm}'."
                if base == "vi":
                    note += " (Note: Kokoro v1.0 does NOT support Vietnamese; verified host macOS voice 'Linh' vi_VN is used.)"
                return (True, "macos_say", chosen, note)
        if req_b == "macos_say":
            return (False, "none", "", f"Requested --voice-backend macos_say unavailable for '{norm}'.")

    if req_b in ("auto", "windows_sapi", "sapi"):
        win_voices = probe_windows_sapi_voices()
        if win_voices:
            candidates = win_voices.get(norm) or win_voices.get(base) or []
            if candidates:
                if req_vid:
                    matched_sapi = next((c for c in candidates if c.lower() == req_vid.lower()), None)
                    if not matched_sapi:
                        return (
                            False,
                            "none",
                            "",
                            f"Requested --voice-id '{req_vid}' not found in Windows SAPI voices for '{norm}': {candidates}",
                        )
                    chosen = matched_sapi
                else:
                    preferred_order = {
                        "en": ["Microsoft David Desktop", "Microsoft Zira Desktop", "Microsoft Mark"],
                        "vi": ["Microsoft An"],
                    }.get(base, [])
                    chosen = next((p for p in preferred_order if p in candidates), candidates[0])
                note = (
                    f"Windows System.Speech SAPI verified installed desktop voice '{chosen}' for '{norm}' "
                    f"(non-neural concatenative backend; available={candidates})."
                )
                return (True, "windows_sapi", chosen, note)
        if req_b in ("windows_sapi", "sapi"):
            return (False, "none", "", f"Requested --voice-backend windows_sapi unavailable for '{norm}'.")

    if base == "vi":
        return (
            False,
            "none",
            "",
            "Vietnamese TTS unavailable: Kokoro v1.0 does not cover Vietnamese and no macOS 'vi_VN' voice (Linh) or --voice-file was found.",
        )
    return (
        False,
        "none",
        "",
        f"No verified local TTS model/voice covers language '{lang}'. Provide --voice-file <audio>.",
    )


def ensure_kit_dependencies(kit_dir: Path) -> Tuple[bool, List[str]]:
    """Bootstrap neutral shared kit/node_modules and kit/vendor/gsap.min.js without calling Claude install.sh."""
    notes: List[str] = []
    three_js = kit_dir / "node_modules" / "three" / "build" / "three.module.js"
    pw_dir = kit_dir / "node_modules" / "playwright"
    gsap_js = kit_dir / "vendor" / "gsap.min.js"

    if not three_js.exists() or not pw_dir.exists():
        npm_bin = shutil.which("npm")
        if not npm_bin:
            return False, ["npm is missing; cannot install shared kit/node_modules."]
        subprocess.run([npm_bin, "install", "--silent", "--no-audit", "--no-fund"], cwd=str(kit_dir), check=True)
        notes.append("Installed shared kit/node_modules (three, playwright, @fontsource/montserrat).")

    if not gsap_js.exists():
        gsap_js.parent.mkdir(parents=True, exist_ok=True)
        curl_bin = shutil.which("curl")
        if not curl_bin:
            return False, ["gsap.min.js missing and curl unavailable."]
        subprocess.run(
            [curl_bin, "-fsSL", "https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js", "-o", str(gsap_js)],
            check=True,
        )
        notes.append("Fetched shared kit/vendor/gsap.min.js.")

    return three_js.exists() and pw_dir.exists() and gsap_js.exists(), notes


class DiskBudgetGuard:
    """Target-aware disk headroom guard keeping >= max(4 GiB, 20% of initial free space)."""

    def __init__(self, target_dir: Path, initial_free_bytes: Optional[int] = None) -> None:
        self.target_dir = target_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(str(target_dir))
        self.initial_free_bytes = int(initial_free_bytes if initial_free_bytes is not None else usage.free)
        self.default_headroom_bytes = max(4 * (1024 ** 3), int(self.initial_free_bytes * 0.20))

    @staticmethod
    def estimate_render_bytes(duration_sec: float, native_4k: bool = True, workers: int = 2) -> int:
        # Realistic upper bound for H.264 segment streams + 4K/1080 masters + stems + stills + overhead
        video_bps = 18_000_000 if native_4k else 8_000_000
        stream_bytes = int((video_bps / 8.0) * max(1.0, duration_sec) * 2.4)
        stems_and_stills = 120 * 1024 * 1024 + max(1, workers) * 32 * 1024 * 1024
        return stream_bytes + stems_and_stills

    @staticmethod
    def estimate_ab_demo_bytes(duration_sec: float, workers: int = 2) -> int:
        """Forecast disk usage for Baseline A (1080p) + Enhanced B (1080p preview + native 4K master)."""
        a_1080 = DiskBudgetGuard.estimate_render_bytes(duration_sec, native_4k=False, workers=workers)
        b_full = DiskBudgetGuard.estimate_render_bytes(duration_sec, native_4k=True, workers=workers)
        return a_1080 + b_full + 96 * 1024 * 1024

    def check(self, required_bytes: int, headroom_bytes: Optional[int] = None) -> Dict[str, Any]:
        usage = shutil.disk_usage(str(self.target_dir))
        free_b = int(usage.free)
        headroom = int(headroom_bytes if headroom_bytes is not None else self.default_headroom_bytes)
        needed_total = int(required_bytes) + headroom
        ok = free_b >= needed_total
        return {
            "ok": ok,
            "status": "PASS" if ok else "DISK_BUDGET_BLOCKED",
            "free_bytes": free_b,
            "required_bytes": int(required_bytes),
            "headroom_bytes": headroom,
            "needed_total_bytes": needed_total,
            "free_gb": round(free_b / (1024 ** 3), 2),
        }


def check_disk_quota(target_dir: Path, min_free_gb: float = 1.5) -> Tuple[bool, float, float]:
    target_dir.mkdir(parents=True, exist_ok=True)
    usage = shutil.disk_usage(str(target_dir))
    total_gb = round(usage.total / (1024 ** 3), 2)
    free_gb = round(usage.free / (1024 ** 3), 2)
    return free_gb >= min_free_gb, total_gb, free_gb


def run_preflight(
    project_root: Path,
    selected_skill: Optional[str] = None,
    lang: str = "en",
    user_voice_file: Optional[Path] = None,
    min_free_gb: float = 1.5,
    requested_workers: Optional[int] = None,
    qa_audio_root: Optional[Path] = None,
    voice_mode: str = "auto",
    voice_backend: str = "auto",
) -> PreflightResult:
    errors: List[str] = []
    notes: List[str] = []

    sys_name = platform.system().lower()
    arch = platform.machine()
    cpu_count = os.cpu_count() or 2

    if sys_name == "windows":
        notes.append("Windows detected: WSL2 or native FFmpeg + Node + Playwright Chromium toolchain required.")

    disk_ok, total_gb, free_gb = check_disk_quota(project_root, min_free_gb=min_free_gb)
    if not disk_ok:
        errors.append(
            f"Disk quota check failed: {free_gb:.2f} GiB free is below minimum safe threshold {min_free_gb:.2f} GiB."
        )

    # Conservative worker cap to protect RAM and tight disk quotas (streaming image2pipe keeps temp disk ~0)
    max_safe = 2 if free_gb < 6.0 else min(4, max(2, cpu_count // 2))
    workers = min(requested_workers, max_safe) if requested_workers else max_safe
    workers = max(1, workers)
    notes.append(f"Conservative parallel worker cap set to {workers} (CPU cores={cpu_count}, free disk={free_gb} GiB).")

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    node_path = shutil.which("node")
    if not ffmpeg_path:
        errors.append("ffmpeg not found on PATH.")
    if not ffprobe_path:
        errors.append("ffprobe not found on PATH.")
    if not node_path:
        errors.append("node not found on PATH.")

    upstream_dir = project_root / "vendor" / "claude-animation-skills"
    kit_dir = upstream_dir / "kit"
    upstream_sha = "unknown"
    upstream_clean = False
    if upstream_dir.exists():
        try:
            sha_r = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=str(upstream_dir), capture_output=True, text=True, check=True
            )
            upstream_sha = sha_r.stdout.strip()
            st_r = subprocess.run(
                ["git", "status", "--porcelain"], cwd=str(upstream_dir), capture_output=True, text=True, check=True
            )
            upstream_clean = len(st_r.stdout.strip()) == 0
        except Exception as exc:
            notes.append(f"Could not read git metadata in vendor/claude-animation-skills: {exc}")
    else:
        errors.append(f"Upstream claude-animation-skills missing at {upstream_dir}")

    kit_ready = False
    if kit_dir.exists() and not errors:
        try:
            kit_ready, kit_notes = ensure_kit_dependencies(kit_dir)
            notes.extend(kit_notes)
        except Exception as exc:
            errors.append(f"Shared kit setup failed: {exc}")

    browser_exe = find_browser_executable()
    if not browser_exe:
        errors.append("No Chromium/Chrome executable found. Run `npx playwright install chromium` in kit/.")

    if sys_name == "darwin":
        webgl_backend = "metal"
    elif sys_name == "windows":
        webgl_backend = "d3d11"
    else:
        webgl_backend = "swiftshader"

    if voice_mode == "off":
        v_ok, v_backend, v_id, v_note = True, "off", "", "Voiceover intentionally disabled via --voice-mode off."
    else:
        v_ok, v_backend, v_id, v_note = verify_language_voice_support(
            lang, kit_dir, user_voice_file, requested_backend=voice_backend
        )
    notes.append(v_note)
    if not v_ok:
        errors.append(v_note)

    qa_root_res, qa_status, qa_note = resolve_qa_audio_root(project_root, qa_audio_root)
    notes.append(qa_note)

    from .voice_prosody import get_backend_capabilities

    say_map = probe_macos_say_voices()
    win_map = probe_windows_sapi_voices()
    voice_backends = {
        "requested_lang": lang,
        "requested_backend": voice_backend,
        "selected_backend": v_backend,
        "selected_voice": v_id,
        "backend_capabilities": get_backend_capabilities(v_backend, v_id),
        "kokoro_installed": (kit_dir / "models" / "kokoro-v1.0.onnx").exists(),
        "kokoro_supports_vietnamese": False,
        "macos_say_en_available": bool(say_map.get("en")),
        "macos_say_vi_available": bool(say_map.get("vi")),
        "windows_sapi_en_available": bool(win_map.get("en")),
        "windows_sapi_voices": win_map,
        "parakeet_asr_installed": bool(glob.glob(str(kit_dir / "models" / "sherpa-onnx-nemo-parakeet*"))),
    }

    # Document renderer capabilities per locked skill vs upstream baseline
    native_4k_caps = {
        "upstream_baseline_note": (
            "Upstream quick skills and stick-figure render 1080x1920@30 via HyperFrames/Canvas; "
            "upstream zach-d-films renders 720x1280@30 and upscales to 1080x1920."
        ),
        "director_adapter_native_4k": {
            "stick-figure": "native_2160x3840_vector_canvas2d",
            "graph": "native_2160x3840_svg_dom_dpr2",
            "minimalistic-graphics": "native_2160x3840_svg_dom_dpr2",
            "map-route": "native_2160x3840_webgl_dpr2_or_labeled_upscale",
            "breakdown": "native_2160x3840_webgl_dpr2_or_labeled_upscale",
            "zach-d-films": "native_2160x3840_webgl_or_labeled_lanczos_upscale",
        },
        "selected_skill": selected_skill,
    }

    return PreflightResult(
        ok=(len(errors) == 0 and kit_ready),
        os_name=sys_name,
        arch=arch,
        cpu_count=cpu_count,
        recommended_workers=workers,
        disk_total_gb=total_gb,
        disk_free_gb=free_gb,
        disk_quota_min_gb=min_free_gb,
        ffmpeg_path=ffmpeg_path,
        ffprobe_path=ffprobe_path,
        node_path=node_path,
        browser_executable=browser_exe,
        webgl_backend=webgl_backend,
        kit_ready=kit_ready,
        upstream_sha=upstream_sha,
        upstream_clean=upstream_clean,
        voice_backends=voice_backends,
        native_4k_capabilities=native_4k_caps,
        notes=notes,
        errors=errors,
        qa_audio_root=str(qa_root_res) if qa_root_res else None,
        qa_audio_status=qa_status,
    )
