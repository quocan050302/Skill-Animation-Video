"""Multi-Voice & Expressive Prosody Candidate Evaluator (R2.3).

Synthesizes offline candidate WAVs (`voice_only_A.wav`, `voice_only_B.wav`, plus alternate
installed desktop voices such as `voice_only_Zira.wav`), measures acoustic dynamic contrast
and phrase-seam continuity, builds `voice_ab_probe.wav`, and writes an honest
`VOICE_LISTENING_CHECKLIST.md` keeping `subjective_voice_quality_status = NOT_VERIFIED`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf

from .parse_script import parse_script_and_build_voice
from .preflight import probe_windows_sapi_voices, probe_macos_say_voices, verify_language_voice_support
from .voice_prosody import render_voice_ab_probe


def _measure_max_phrase_step(wav_path: Path) -> float:
    """Detect harsh DC jumps or un-faded sample steps (>0.08 amplitude step between adjacent frames)."""
    data, _ = sf.read(str(wav_path), dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if len(data) < 4:
        return 0.0
    return round(float(np.max(np.abs(np.diff(data)))), 4)


def evaluate_voice_candidates(
    raw_script: str,
    out_dir: Path,
    kit_dir: Path,
    lang: str = "en",
    selected_skill: str = "zach-d-films",
    voice_style_b: str = "cinematic",
    voice_pause_strength: float = 1.0,
) -> Dict[str, Any]:
    """Generate clean A/B + alternate installed candidate WAVs and subjective listening checklist."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Baseline Version A (legacy single-pace delivery)
    run_a = parse_script_and_build_voice(
        raw_script=raw_script,
        selected_skill=selected_skill,
        run_dir=out_dir / "_cand_A",
        kit_dir=kit_dir,
        lang=lang,
        voice_style="legacy",
        voice_pause_strength=voice_pause_strength,
    )
    wav_a = out_dir / "voice_only_A.wav"
    shutil.copy2(run_a["voice"]["vo_wav_path"], wav_a)

    # 2. Primary Enhanced Version B (cinematic prosody delivery)
    run_b = parse_script_and_build_voice(
        raw_script=raw_script,
        selected_skill=selected_skill,
        run_dir=out_dir / "_cand_B",
        kit_dir=kit_dir,
        lang=lang,
        voice_style=voice_style_b,
        voice_pause_strength=voice_pause_strength,
    )
    wav_b = out_dir / "voice_only_B.wav"
    shutil.copy2(run_b["voice"]["vo_wav_path"], wav_b)

    rep_a = run_a["voice"]["voice_delivery_report"]
    rep_b = run_b["voice"]["voice_delivery_report"]
    probe_meta = render_voice_ab_probe(
        legacy_wav=wav_a,
        enhanced_wav=wav_b,
        out_wav=out_dir / "voice_ab_probe.wav",
        report_a=rep_a,
        report_b=rep_b,
    )

    candidates_summary: List[Dict[str, Any]] = [
        {
            "candidate_id": "A_legacy",
            "voice_id": run_a["voice"]["voice_id"],
            "voice_style": "legacy",
            "wav_path": str(wav_a.resolve()),
            "duration_sec": run_a["voice"]["vo_duration_sec"],
            "neural_prosody": False,
            "summary_metrics": rep_a.get("summary_metrics"),
            "max_sample_step": _measure_max_phrase_step(wav_a),
        },
        {
            "candidate_id": "B_primary",
            "voice_id": run_b["voice"]["voice_id"],
            "voice_style": voice_style_b,
            "wav_path": str(wav_b.resolve()),
            "duration_sec": run_b["voice"]["vo_duration_sec"],
            "neural_prosody": bool(rep_b.get("neural_prosody", False)),
            "summary_metrics": rep_b.get("summary_metrics"),
            "max_sample_step": _measure_max_phrase_step(wav_b),
        },
    ]

    # 3. Alternate installed voice candidate (e.g., Microsoft Zira Desktop on Windows SAPI5)
    norm_base = lang.strip().lower().replace("_", "-").split("-")[0]
    alt_voice_id: Optional[str] = None
    win_voices = probe_windows_sapi_voices()
    if win_voices:
        avail = win_voices.get(norm_base) or []
        alt_voice_id = next((v for v in avail if v != run_b["voice"]["voice_id"]), None)
    else:
        say_voices = probe_macos_say_voices()
        avail = say_voices.get(norm_base) or []
        alt_voice_id = next((v for v in avail if v != run_b["voice"]["voice_id"]), None)

    if alt_voice_id:
        run_alt = parse_script_and_build_voice(
            raw_script=raw_script,
            selected_skill=selected_skill,
            run_dir=out_dir / "_cand_alt",
            kit_dir=kit_dir,
            lang=lang,
            voice_style=voice_style_b,
            voice_id=alt_voice_id,
            voice_pause_strength=voice_pause_strength,
        )
        short_tag = alt_voice_id.replace("Microsoft ", "").replace(" Desktop", "").split()[0]
        wav_alt = out_dir / f"voice_only_{short_tag}.wav"
        shutil.copy2(run_alt["voice"]["vo_wav_path"], wav_alt)
        rep_alt = run_alt["voice"]["voice_delivery_report"]
        candidates_summary.append({
            "candidate_id": f"C_alt_{short_tag}",
            "voice_id": alt_voice_id,
            "voice_style": voice_style_b,
            "wav_path": str(wav_alt.resolve()),
            "duration_sec": run_alt["voice"]["vo_duration_sec"],
            "neural_prosody": bool(rep_alt.get("neural_prosody", False)),
            "summary_metrics": rep_alt.get("summary_metrics"),
            "max_sample_step": _measure_max_phrase_step(wav_alt),
        })

    # Honest capability report noting offline absence of neural TTS weights
    _, backend_name, active_voice, _ = verify_language_voice_support(lang, kit_dir)
    eval_payload = {
        "schema_version": "sd-voice-candidate-eval-1",
        "backend": backend_name,
        "primary_voice_id": active_voice,
        "subjective_voice_quality_status": "NOT_VERIFIED",
        "neural_tts_offline_status": "UNAVAILABLE (kokoro_onnx/piper/edge_tts offline weights absent; Windows SAPI5 desktop voices only)",
        "ab_probe": probe_meta,
        "candidates": candidates_summary,
    }
    eval_json_p = out_dir / "voice_candidate_evaluation.json"
    eval_json_p.write_text(json.dumps(eval_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Voice Candidate Listening & Comparison Checklist",
        "",
        "- **Subjective Voice Quality Status**: `NOT_VERIFIED` (Automated metrics measure modulation, clipping & seam Continuity ONLY; a human listener must judge naturalness/storytelling warmth).",
        f"- **Host Acoustic Engine**: `{backend_name}` (`neural_prosody = False`, concatenative desktop speech)",
        "",
        "## Generated Candidate Files",
        "| Candidate | Voice ID | Style | Duration | WPS Span | RMS Span | F0 Span | Max Step | File |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for c in candidates_summary:
        sm = c.get("summary_metrics") or {}
        md_lines.append(
            f"| `{c['candidate_id']}` | `{c['voice_id']}` | `{c['voice_style']}` | {c['duration_sec']:.2f}s | "
            f"{sm.get('wps_dynamic_span_pct', 0)}% | {sm.get('rms_dynamic_span_db', 0)} dB | "
            f"{sm.get('f0_median_span_hz', 0)} Hz | {c['max_sample_step']} | `{Path(c['wav_path']).name}` |"
        )
    md_lines.extend([
        "",
        "## Human Listening Prompts",
        "1. Listen to `voice_ab_probe.wav` (A -> chime -> B): verify phrase transitions have zero click/pop seams (12ms raised-cosine envelope).",
        "2. Check anticipation pause before *'those tank walls finally gave way'* and solemn slowing on *'Twenty-one people died and about 150 were injured.'*",
        "3. Compare primary voice (`voice_only_B.wav`) against companion voice (e.g. `voice_only_Zira.wav`) before selecting `--voice-id` or supplying `--voice-file <recording.wav>`.",
    ])
    checklist_p = out_dir / "VOICE_LISTENING_CHECKLIST.md"
    checklist_p.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return {
        "eval_json": str(eval_json_p.resolve()),
        "checklist_md": str(checklist_p.resolve()),
        "voice_ab_probe_wav": str((out_dir / "voice_ab_probe.wav").resolve()),
        "payload": eval_payload,
    }
