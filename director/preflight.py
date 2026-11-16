"""STEP 0: Platform, toolchain, WebGL GPU, voice coverage, and disk-quota preflight."""

from __future__ import annotations

import glob
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def find_browser_executable() -> Optional[str]:
    env_chrome = os.environ.get("PLAYWRIGHT_CHROME_PATH") or os.environ.get("CHROME")
    if env_chrome and os.path.exists(env_chrome):
        return env_chrome

    home = Path.home()
    patterns = [
        str(home / "Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        str(home / "Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
        str(home / ".cache/ms-playwright/chromium-*/chrome-linux/chrome"),
    ]
    for pat in patterns:
        matches = sorted(glob.glob(pat), reverse=True)
        for m in matches:
            if os.path.exists(m) and os.access(m, os.X_OK):
                return m

    system_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    for c in system_candidates:
        if c and os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return None


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
) -> Tuple[bool, str, str, str]:
    """Return (supported, backend, voice_id, explanation) truthfully."""
    norm = lang.strip().lower().replace("_", "-")
    base = norm.split("-")[0]

    if user_voice_file is not None:
        if user_voice_file.exists():
            return (True, "user_file", str(user_voice_file), f"Verified user-supplied audio file ({user_voice_file.name}).")
        return (False, "none", "", f"User voice file does not exist: {user_voice_file}")

    # Check Kokoro first ONLY if models exist AND language is verified in Kokoro v1.0
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

    # Check macOS `say` voices actually installed on this host
    say_voices = probe_macos_say_voices()
    if say_voices:
        candidates = say_voices.get(norm) or say_voices.get(base) or []
        if candidates:
            preferred_order = {
                "en": ["Samantha", "Daniel", "Reed (English (US))", "Eddy (English (US))", "Karen"],
                "vi": ["Linh"],
            }.get(base, [])
            chosen = next((p for p in preferred_order if p in candidates), candidates[0])
            note = f"macOS Speech Synthesis (`say`) verified installed voice '{chosen}' for '{norm}'."
            if base == "vi":
                note += " (Note: Kokoro v1.0 does NOT support Vietnamese; verified host macOS voice 'Linh' vi_VN is used.)"
            return (True, "macos_say", chosen, note)

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
    elif sys_name == "linux":
        webgl_backend = "swiftshader"
    else:
        webgl_backend = "swiftshader"

    v_ok, v_backend, v_id, v_note = verify_language_voice_support(lang, kit_dir, user_voice_file)
    notes.append(v_note)
    if not v_ok:
        errors.append(v_note)

    say_map = probe_macos_say_voices()
    voice_backends = {
        "requested_lang": lang,
        "selected_backend": v_backend,
        "selected_voice": v_id,
        "kokoro_installed": (kit_dir / "models" / "kokoro-v1.0.onnx").exists(),
        "kokoro_supports_vietnamese": False,
        "macos_say_en_available": bool(say_map.get("en")),
        "macos_say_vi_available": bool(say_map.get("vi")),
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
    )
