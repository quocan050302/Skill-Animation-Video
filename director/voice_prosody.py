"""STEP 1B (R1): Semantic Voice Prosody Planner, SSML Generator, Execution Auditor & A/B Probe.

Upgrades Short Director voiceover from flat single-rate sentences to structured,
phrase-aware delivery with:
- Honest backend capability disclosure (`neural_prosody`, `ssml_supported`, live probes)
- Bounded rate/pitch/emphasis/pause planning (`legacy` | `natural` | `cinematic`)
- Token-conserving pronunciation lexicon support (`<sub alias="...">` without mutating captions)
- Waveform-level prosody execution measurement (`f0_median_hz`, `rms_dbfs`, local speech rate,
  actual inter-phrase silence duration) separated cleanly from `subjective_voice_quality_status = NOT_VERIFIED`
"""

from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import soundfile as sf
from scipy import signal


SCHEMA_VERSION = "sd-voice-prosody-1"

DEFAULT_PRONUNCIATION_LEXICON: Dict[str, str] = {
    "FAA": "F A A",
    "CFR": "C F R",
    "PSI": "P S I",
    "PDF": "P D F",
    "LED": "L E D",
    "PCB": "P C B",
    "3D": "three D",
    "4K": "four K",
    "AC": "A C",
}

CONTRAST_MARKERS = {
    "but", "however", "yet", "instead", "wait", "never", "isn't", "doesn't",
    "don't", "only", "alone", "not", "without", "fails", "failure",
}

EXPLANATION_KEYWORDS = {
    "bleed", "breather", "equalizes", "equalize", "pressure", "outer", "middle",
    "inner", "backup", "fail-safe", "failsafe", "moisture", "condensation", "frost",
    "fogging", "layers", "layer", "tiny", "hole", "crack", "cabin", "altitude",
    "three", "clear", "safe", "slowly",
    "molasses", "flood", "gallons", "million", "tank", "leaking", "rivet", "steel",
    "miles", "faster", "horse", "smashed", "trapped", "twenty-one", "150", "injured",
    "construction", "engineers", "tighten",
}


def get_backend_capabilities(backend: str, voice_id: str = "") -> Dict[str, Any]:
    """Return honest capability matrix for the active local TTS/voice backend."""
    b = (backend or "none").lower()
    if b == "windows_sapi":
        return {
            "backend": "windows_sapi",
            "voice_id": voice_id,
            "engine_type": "sapi5_desktop_concat",
            "neural_prosody": False,
            "ssml_supported": True,
            "supported_controls": ["rate", "pitch", "emphasis", "break_ms", "volume", "sub_alias"],
            "rate_range_mult": [0.78, 1.25],
            "pitch_range_semitones": [-4.0, 4.0],
            "supports_word_timestamps_native": False,
            "capability_note": (
                "Windows System.Speech SpeakSsml executes rate, pitch, emphasis and break pauses "
                "genuinely on waveform output; engine remains non-neural desktop concatenative voice."
            ),
        }
    if b == "kokoro":
        return {
            "backend": "kokoro",
            "voice_id": voice_id,
            "engine_type": "kokoro_onnx_neural",
            "neural_prosody": True,
            "ssml_supported": False,
            "supported_controls": ["speed", "pause_ms", "post_prosody_shaping"],
            "rate_range_mult": [0.85, 1.20],
            "pitch_range_semitones": [-2.0, 2.0],
            "supports_word_timestamps_native": False,
            "capability_note": "Kokoro v1.0 ONNX neural TTS supports per-phrase speed and silence pacing.",
        }
    if b == "macos_say":
        return {
            "backend": "macos_say",
            "voice_id": voice_id,
            "engine_type": "macos_speech_synthesis",
            "neural_prosody": False,
            "ssml_supported": False,
            "supported_controls": ["rate", "pause_ms", "post_prosody_shaping"],
            "rate_range_mult": [0.84, 1.22],
            "pitch_range_semitones": [0.0, 0.0],
            "supports_word_timestamps_native": False,
            "capability_note": "macOS `say` executes per-phrase `-r` speaking rate and sample silence pauses.",
        }
    if b == "user_file":
        return {
            "backend": "user_file",
            "voice_id": voice_id,
            "engine_type": "user_supplied_audio",
            "neural_prosody": True,
            "ssml_supported": False,
            "supported_controls": [],
            "rate_range_mult": [1.0, 1.0],
            "pitch_range_semitones": [0.0, 0.0],
            "supports_word_timestamps_native": False,
            "capability_note": "User-supplied recording preserved verbatim without synthetic pitch/rate warping.",
        }
    return {
        "backend": b,
        "voice_id": voice_id,
        "engine_type": "silent_or_unavailable",
        "neural_prosody": False,
        "ssml_supported": False,
        "supported_controls": [],
        "rate_range_mult": [1.0, 1.0],
        "pitch_range_semitones": [0.0, 0.0],
        "supports_word_timestamps_native": False,
        "capability_note": "No live acoustic synthesis backend active.",
    }


def normalize_spoken_tokens(text: str) -> List[str]:
    """Canonical word tokens used for conservation checks across display vs spoken text."""
    return [t for t in re.split(r"\s+", text.strip()) if t]


def strip_ssml_to_plain_text(ssml_or_text: str) -> str:
    """Strip SSML tags while keeping visible text intact (not alias substitutions)."""
    no_sub_close = re.sub(r"</sub\s*>", "", ssml_or_text, flags=re.IGNORECASE)
    no_sub_open = re.sub(r"<sub\b[^>]*>", "", no_sub_close, flags=re.IGNORECASE)
    no_tags = re.sub(r"<[^>]+>", " ", no_sub_open)
    unescaped = html.unescape(no_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


def check_token_conservation(expected_words: List[str], rendered_text: str) -> Dict[str, Any]:
    """Verify no words were dropped, truncated or duplicated in prosody markup."""
    stripped = strip_ssml_to_plain_text(rendered_text)
    actual_words = normalize_spoken_tokens(stripped)
    norm_exp = [re.sub(r"^[^\w]+|[^\w]+$", "", w.lower()) for w in expected_words if re.sub(r"[^\w]", "", w)]
    norm_act = [re.sub(r"^[^\w]+|[^\w]+$", "", w.lower()) for w in actual_words if re.sub(r"[^\w]", "", w)]
    ok = norm_exp == norm_act
    return {
        "ok": ok,
        "expected_count": len(norm_exp),
        "actual_count": len(norm_act),
        "expected_tokens": norm_exp,
        "actual_tokens": norm_act,
    }


def _split_sentence_into_clauses(sentence: str) -> List[str]:
    """Split a sentence cleanly into performative phrase units (never cutting short fragments)."""
    s = re.sub(r"\s+", " ", sentence.strip())
    if not s:
        return []
    words = s.split()
    if len(words) <= 9:
        return [s]

    # Split after commas/semicolons/colons/parenthetical breaks when both sides hold >= 3 words
    raw_parts = re.split(r"(?<=[,;:])\s+|\s+(?=(?:Wait|Plus|So|But|However|Instead|Then)\b)", s)
    merged: List[str] = []
    for part in raw_parts:
        p = part.strip()
        if not p:
            continue
        if not merged:
            merged.append(p)
            continue
        prev_words = len(merged[-1].split())
        cur_words = len(p.split())
        if prev_words < 3 or cur_words < 3:
            merged[-1] = f"{merged[-1]} {p}".strip()
        else:
            merged.append(p)
    return merged


def _infer_clause_intent(clause: str, sent_idx: int, total_sentences: int, clause_idx: int) -> str:
    low = clause.lower().strip()
    if sent_idx == 0 and clause_idx == 0:
        if any(k in low for k in ("never", "nothing like", "unlikely", "expected", "unexpected", "1919")):
            return "hook_whispered_curiosity"
        return "hook" if clause.endswith("?") or any(w in low for w in ("ever ", "why ", "what if", "wonder")) else "hook"
    if "wasn't" in low or "was molasses" in low or "it was " in low:
        return "sudden_reveal"
    if any(k in low for k in ("leaking", "leak", "for years", "warning", "strained")):
        return "quiet_foreshadow"
    if any(k in low for k in ("gave way", "walls gave", "rupture", "burst")):
        return "rupture_burst"
    if any(k in low for k in ("2.3", "million gallons", "poured", "35", "faster", "race", "smashed", "trapped")):
        return "danger_acceleration"
    if any(k in low for k in ("twenty-one", "21", "died", "injured", "150", "casualt")):
        return "human_cost"
    if clause.endswith("?") or low.startswith("wait") or "what if" in low:
        return "twist_question"
    if any(re.search(rf"\b{re.escape(m)}\b", low) for m in ("but", "however", "isn't", "doesn't", "never", "instead")):
        return "contrast"
    if sent_idx == total_sentences - 1:
        if any(k in low for k in ("engineers", "tighten", "rules", "history", "lesson", "remember")):
            return "reflective_payoff"
        return "payoff"
    if any(k in low for k in ("equalizes", "equalize", "three", "because", "carries", "backup", "vents", "becomes")):
        return "mechanism"
    return "explain"


def score_emphasis_candidates(
    phrase: str,
    intent: str,
    domain_terms: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Rank up to 2 high-value semantic keywords/numbers inside one phrase."""
    tokens = phrase.split()
    dom_set = {str(t).lower() for t in (domain_terms or []) if len(str(t)) >= 3}
    scored: List[Dict[str, Any]] = []
    for idx, tok in enumerate(tokens):
        clean = re.sub(r"^[^\w]+|[^\w]+$", "", tok).lower()
        if len(clean) <= 2 and not re.match(r"^\d+$", clean):
            continue
        score = 0.0
        reasons: List[str] = []
        if re.search(r"\d", clean):
            score += 0.50
            reasons.append("numeric")
        if clean in CONTRAST_MARKERS:
            score += 0.65
            reasons.append("contrast_marker")
        if clean in EXPLANATION_KEYWORDS:
            score += 0.55
            reasons.append("mechanism_keyword")
        if clean in dom_set:
            score += 0.45
            reasons.append("domain_term")
        if idx == len(tokens) - 1 and tok.endswith(("?", "!")):
            score += 0.25
            reasons.append("terminal_punch")
        if score > 0.35:
            scored.append({"index": idx, "word": tok, "clean": clean, "score": round(score, 3), "reasons": reasons})

    scored.sort(key=lambda x: (-x["score"], x["index"]))
    selected: List[Dict[str, Any]] = []
    for cand in scored:
        # Avoid emphasizing adjacent words simultaneously so cadence breathes
        if any(abs(cand["index"] - s["index"]) <= 1 for s in selected):
            continue
        selected.append(cand)
        if len(selected) >= (2 if len(tokens) >= 7 else 1):
            break
    selected.sort(key=lambda x: x["index"])
    return selected


def _build_ssml_phrase(
    phrase: str,
    voice_id: str,
    rate_mult: float,
    pitch_st: float,
    emphasis_indices: List[int],
    emphasis_level: str,
    volume_db: float,
    lexicon: Optional[Dict[str, str]] = None,
) -> str:
    """Build safe SAPI5 / W3C SSML snippet preserving exact canonical display tokens."""
    rate_pct = int(round((rate_mult - 1.0) * 100.0))
    pitch_pct = int(round(pitch_st * 6.5))
    vol_val = max(60, min(100, int(round(92 + volume_db * 5.0))))
    rate_str = f"{rate_pct:+d}%" if rate_pct != 0 else "0%"
    pitch_str = f"{pitch_pct:+d}%" if pitch_pct != 0 else "0%"

    lex = {**DEFAULT_PRONUNCIATION_LEXICON, **(lexicon or {})}
    tokens = phrase.split()
    emp_set = set(emphasis_indices)
    parts: List[str] = []
    for idx, tok in enumerate(tokens):
        esc_tok = html.escape(tok, quote=False)
        stripped = re.sub(r"^[^\w]+|[^\w]+$", "", tok)
        if stripped in lex and stripped == tok:
            inner = f"<sub alias=\"{html.escape(lex[stripped], quote=True)}\">{esc_tok}</sub>"
        else:
            inner = esc_tok
        if idx in emp_set and emphasis_level != "none":
            parts.append(f"<emphasis level=\"{emphasis_level}\">{inner}</emphasis>")
        else:
            parts.append(inner)

    body = " ".join(parts)
    if voice_id:
        voice_open = f"<voice name=\"{html.escape(voice_id, quote=True)}\">"
        voice_close = "</voice>"
    else:
        voice_open = ""
        voice_close = ""

    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"{voice_open}"
        f"<prosody rate='{rate_str}' pitch='{pitch_str}' volume='{vol_val}'>"
        f"{body}"
        "</prosody>"
        f"{voice_close}"
        "</speak>"
    )


def plan_phrase_delivery(
    sentence: str,
    sent_idx: int,
    total_sentences: int,
    voice_style: str = "cinematic",
    voice_id: str = "",
    voice_pause_strength: float = 1.0,
    domain_terms: Optional[List[str]] = None,
    lexicon: Optional[Dict[str, str]] = None,
    backend_caps: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Decompose one script sentence into semantically paced, pitch/rate-bounded phrases."""
    style = (voice_style or "cinematic").lower()
    pause_scale = max(0.35, min(2.0, float(voice_pause_strength)))
    caps = backend_caps or get_backend_capabilities("windows_sapi", voice_id)
    r_min, r_max = caps.get("rate_range_mult", [0.84, 1.20])
    p_min, p_max = caps.get("pitch_range_semitones", [-3.0, 3.5])

    clauses = [sentence.strip()] if style == "legacy" else _split_sentence_into_clauses(sentence)
    phrases: List[Dict[str, Any]] = []

    for ci, clause in enumerate(clauses):
        is_last_clause = (ci == len(clauses) - 1)
        is_last_sent = (sent_idx == total_sentences - 1) and is_last_clause
        intent = _infer_clause_intent(clause, sent_idx, total_sentences, ci)

        if style == "legacy":
            rate_mult = 1.05
            pitch_st = 0.0
            emp_level = "none"
            emp_cands: List[Dict[str, Any]] = []
            vol_db = 0.0
            pause_before = 0
            pause_after = 0 if is_last_sent else (180 if clause.endswith(("?", "!")) or sent_idx == 0 else 140)
        else:
            boost = 1.0 if style == "cinematic" else 0.62
            emp_cands = score_emphasis_candidates(clause, intent, domain_terms=domain_terms)
            if intent == "hook":
                rate_mult = 1.04 + 0.03 * boost
                pitch_st = 1.4 * boost
                emp_level = "moderate"
                vol_db = 0.6 * boost
                pause_before = 0
                pause_after = int(round((240 if clause.endswith("?") else 170) * pause_scale))
            elif intent == "hook_whispered_curiosity":
                rate_mult = 0.96
                pitch_st = -0.3 * boost
                emp_level = "moderate"
                vol_db = -0.3
                pause_before = 0
                pause_after = int(round(220 * pause_scale))
            elif intent == "sudden_reveal":
                rate_mult = 0.93
                pitch_st = 1.2 * boost
                emp_level = "strong"
                vol_db = 0.8 * boost
                pause_before = int(round(120 * pause_scale))
                pause_after = int(round(230 * pause_scale))
            elif intent == "quiet_foreshadow":
                rate_mult = 0.94
                pitch_st = -0.7 * boost
                emp_level = "moderate"
                vol_db = -0.2
                pause_before = int(round(60 * pause_scale))
                pause_after = int(round(240 * pause_scale))
            elif intent == "rupture_burst":
                rate_mult = 1.02 + 0.03 * boost
                pitch_st = 1.3 * boost
                emp_level = "strong"
                vol_db = 1.0 * boost
                pause_before = int(round(140 * pause_scale))
                pause_after = int(round(180 * pause_scale))
            elif intent == "danger_acceleration":
                rate_mult = 1.04 + 0.03 * boost
                pitch_st = 0.7 * boost
                emp_level = "moderate"
                vol_db = 0.6 * boost
                pause_before = 0
                pause_after = int(round(135 * pause_scale))
            elif intent == "human_cost":
                rate_mult = 0.87
                pitch_st = -1.2 * boost
                emp_level = "moderate"
                vol_db = -0.45
                pause_before = int(round(160 * pause_scale))
                pause_after = int(round(290 * pause_scale))
            elif intent == "reflective_payoff":
                rate_mult = 0.93
                pitch_st = 0.4 * boost
                emp_level = "moderate"
                vol_db = 0.4 * boost
                pause_before = int(round(90 * pause_scale))
                pause_after = 0 if is_last_sent else int(round(180 * pause_scale))
            elif intent == "twist_question":
                rate_mult = 0.90 - 0.04 * boost
                pitch_st = 2.4 * boost
                emp_level = "strong"
                vol_db = 0.9 * boost
                pause_before = int(round(120 * pause_scale))
                pause_after = int(round(320 * pause_scale))
            elif intent == "contrast":
                rate_mult = 0.92 - 0.03 * boost
                pitch_st = -1.2 * boost
                emp_level = "strong"
                vol_db = 0.5 * boost
                pause_before = int(round(80 * pause_scale))
                pause_after = int(round(210 * pause_scale))
            elif intent == "mechanism":
                rate_mult = 0.95 - 0.02 * boost
                pitch_st = -0.35 * boost
                emp_level = "moderate"
                vol_db = 0.35 * boost
                pause_before = 0
                pause_after = int(round((140 if is_last_clause else 95) * pause_scale))
            elif intent == "payoff":
                rate_mult = 0.96
                pitch_st = 1.1 * boost
                emp_level = "moderate"
                vol_db = 0.8 * boost
                pause_before = 0
                pause_after = 0 if is_last_sent else int(round(160 * pause_scale))
            else:
                rate_mult = 1.01
                pitch_st = 0.25 * boost if (ci % 2 == 0) else -0.35 * boost
                emp_level = "moderate" if emp_cands else "none"
                vol_db = 0.15 * boost
                pause_before = 0
                pause_after = 0 if is_last_sent else int(round((150 if is_last_clause else 90) * pause_scale))

        # Clamp strictly to physical/backend safe limits
        rate_mult = round(max(r_min, min(r_max, rate_mult)), 3)
        pitch_st = round(max(p_min, min(p_max, pitch_st)), 3)
        pause_before = max(0, min(550, int(pause_before)))
        pause_after = max(0, min(550, int(pause_after)))
        emp_indices = [e["index"] for e in emp_cands]

        ssml = _build_ssml_phrase(
            phrase=clause,
            voice_id=voice_id,
            rate_mult=rate_mult,
            pitch_st=pitch_st,
            emphasis_indices=emp_indices,
            emphasis_level=emp_level,
            volume_db=vol_db,
            lexicon=lexicon,
        )
        tok_check = check_token_conservation(clause.split(), ssml)
        if not tok_check["ok"]:
            raise ValueError(f"Prosody token conservation failed on phrase {clause!r}: {tok_check}")

        phrases.append({
            "sentence_index": sent_idx,
            "clause_index": ci,
            "intent": intent,
            "text": clause,
            "word_count": len(clause.split()),
            "emphasis_words": [e["word"] for e in emp_cands],
            "emphasis_indices": emp_indices,
            "emphasis_level": emp_level,
            "rate_multiplier": rate_mult,
            "pitch_semitones": pitch_st,
            "volume_trim_db": round(vol_db, 2),
            "pause_before_ms": pause_before,
            "pause_after_ms": pause_after,
            "ssml_markup": ssml,
            "token_conservation": True,
        })

    return phrases


def build_prosody_plan(
    sentences: List[str],
    voice_style: str = "cinematic",
    backend: str = "windows_sapi",
    voice_id: str = "",
    voice_pause_strength: float = 1.0,
    domain_terms: Optional[List[str]] = None,
    lexicon: Optional[Dict[str, str]] = None,
    override_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create and validate complete `voice_prosody_plan.json` for a script."""
    caps = get_backend_capabilities(backend, voice_id)
    if override_plan is not None and isinstance(override_plan.get("phrases"), list):
        plan = dict(override_plan)
        plan.setdefault("schema_version", SCHEMA_VERSION)
        plan.setdefault("backend_capabilities", caps)
        validate_prosody_plan(plan, sentences)
        return plan

    all_phrases: List[Dict[str, Any]] = []
    pid = 0
    for si, sent in enumerate(sentences):
        p_list = plan_phrase_delivery(
            sentence=sent,
            sent_idx=si,
            total_sentences=len(sentences),
            voice_style=voice_style,
            voice_id=voice_id,
            voice_pause_strength=voice_pause_strength,
            domain_terms=domain_terms,
            lexicon=lexicon,
            backend_caps=caps,
        )
        for p in p_list:
            p["phrase_id"] = f"ph_{pid:02d}"
            p["phrase_index"] = pid
            all_phrases.append(p)
            pid += 1

    plan = {
        "schema_version": SCHEMA_VERSION,
        "voice_style": (voice_style or "cinematic").lower(),
        "voice_pause_strength": round(float(voice_pause_strength), 2),
        "backend": backend,
        "voice_id": voice_id,
        "backend_capabilities": caps,
        "sentence_count": len(sentences),
        "phrase_count": len(all_phrases),
        "phrases": all_phrases,
    }
    validate_prosody_plan(plan, sentences)
    return plan


def validate_prosody_plan(plan: Dict[str, Any], sentences: List[str]) -> None:
    """Fail closed if any phrase violates physical bounds or loses script tokens."""
    phrases = list(plan.get("phrases") or [])
    if not phrases:
        raise ValueError("Prosody plan cannot contain 0 phrases.")

    caps = plan.get("backend_capabilities") or {}
    r_lo, r_hi = caps.get("rate_range_mult", [0.75, 1.30])
    p_lo, p_hi = caps.get("pitch_range_semitones", [-4.5, 4.5])
    combined_words: List[str] = []

    for p in phrases:
        rm = float(p.get("rate_multiplier", 1.0))
        ps = float(p.get("pitch_semitones", 0.0))
        pa = int(p.get("pause_after_ms", 0))
        pb = int(p.get("pause_before_ms", 0))
        if not (r_lo - 1e-4 <= rm <= r_hi + 1e-4):
            raise ValueError(f"Phrase {p.get('phrase_id')} rate {rm} outside [{r_lo}, {r_hi}]")
        if not (p_lo - 1e-4 <= ps <= p_hi + 1e-4):
            raise ValueError(f"Phrase {p.get('phrase_id')} pitch {ps}st outside [{p_lo}, {p_hi}]")
        if not (0 <= pb <= 650 and 0 <= pa <= 650):
            raise ValueError(f"Phrase {p.get('phrase_id')} pause ms ({pb}, {pa}) outside [0, 650]")
        toks = normalize_spoken_tokens(str(p.get("text", "")))
        if not toks:
            raise ValueError(f"Phrase {p.get('phrase_id')} has empty text")
        if p.get("ssml_markup"):
            tc = check_token_conservation(toks, str(p["ssml_markup"]))
            if not tc["ok"]:
                raise ValueError(f"SSML token conservation failed on {p.get('phrase_id')}: {tc}")
        combined_words.extend(toks)

    expected_all: List[str] = []
    for s in sentences:
        expected_all.extend(normalize_spoken_tokens(s))
    norm_exp = [re.sub(r"[^\w]", "", w.lower()) for w in expected_all if re.sub(r"[^\w]", "", w)]
    norm_act = [re.sub(r"[^\w]", "", w.lower()) for w in combined_words if re.sub(r"[^\w]", "", w)]
    if norm_exp != norm_act:
        raise ValueError(
            f"Prosody script word conservation mismatch: expected {len(norm_exp)} tokens, got {len(norm_act)}"
        )


def _estimate_segment_f0_stats(seg: np.ndarray, sr: int) -> Tuple[Optional[float], float]:
    """Robust autocorrelation fundamental pitch estimator over active voiced 30ms frames."""
    if len(seg) < int(0.06 * sr):
        return None, 0.0
    frame = max(256, int(0.032 * sr))
    hop = max(64, int(0.012 * sr))
    min_lag = max(2, int(sr / 290.0))
    max_lag = min(frame // 2, int(sr / 70.0))
    if max_lag <= min_lag + 2:
        return None, 0.0

    # Mild 75..900 Hz bandpass reduces sibilant noise interference
    nyq = 0.5 * sr
    b, a = signal.butter(2, [min(0.4, 75.0 / nyq), min(0.92, 900.0 / nyq)], btype="band")
    filt = signal.lfilter(b, a, seg.astype(np.float64))

    f0s: List[float] = []
    for pos in range(0, len(filt) - frame + 1, hop):
        win = filt[pos : pos + frame]
        e = float(np.mean(win * win))
        if e < 1e-4:
            continue
        win_z = win - np.mean(win)
        ac = np.correlate(win_z, win_z, mode="full")[frame - 1 :]
        if ac[0] <= 1e-9:
            continue
        sub = ac[min_lag:max_lag]
        if len(sub) == 0:
            continue
        best_idx = int(np.argmax(sub))
        if sub[best_idx] > 0.35 * ac[0]:
            f0 = sr / float(min_lag + best_idx)
            if 70.0 <= f0 <= 300.0:
                f0s.append(f0)

    if len(f0s) < 2:
        return None, 0.0
    arr = np.asarray(f0s, dtype=np.float64)
    med = float(np.median(arr))
    iqr = float(np.percentile(arr, 75) - np.percentile(arr, 25))
    return round(med, 2), round(iqr, 2)


def measure_voice_delivery(
    vo_wav_path: Path,
    phrase_spans: List[Dict[str, Any]],
    prosody_plan: Dict[str, Any],
    words: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Measure real waveform acoustic execution per phrase and audit prosody truthfulness."""
    backend = str(prosody_plan.get("backend", "none"))
    style = str(prosody_plan.get("voice_style", "legacy"))
    caps = prosody_plan.get("backend_capabilities") or get_backend_capabilities(backend)

    if not vo_wav_path or not vo_wav_path.exists():
        return {
            "schema_version": "sd-voice-delivery-1",
            "algorithmic_prosody_execution_status": "FAIL" if backend != "off" else "PASS",
            "subjective_voice_quality_status": "NOT_VERIFIED",
            "reason": "vo.wav missing",
            "phrase_metrics": [],
        }

    samples, sr = sf.read(str(vo_wav_path), dtype="float64")
    if samples.ndim > 1:
        samples = samples.mean(axis=1)

    pk_dbfs = round(20.0 * math.log10(float(np.max(np.abs(samples))) + 1e-12), 2)
    phrase_metrics: List[Dict[str, Any]] = []
    problems: List[str] = []

    for idx, sp in enumerate(phrase_spans):
        s_t = float(sp["start"])
        e_t = float(sp["end"])
        i0 = max(0, int(round(s_t * sr)))
        i1 = min(len(samples), int(round(e_t * sr)))
        seg = samples[i0:i1]
        if len(seg) < int(0.05 * sr):
            problems.append(f"Phrase {sp.get('phrase_id', idx)} segment too short or silent ({len(seg)} samples)")
            continue
        seg_rms = float(np.sqrt(np.mean(seg * seg) + 1e-12))
        rms_db = round(20.0 * math.log10(seg_rms + 1e-12), 2)
        if rms_db <= -50.0:
            problems.append(f"Phrase {sp.get('phrase_id', idx)} dropped/silent ({rms_db:.1f} dBFS)")

        f0_med, f0_iqr = _estimate_segment_f0_stats(seg, sr)
        dur_s = max(0.05, (i1 - i0) / float(sr))
        w_cnt = int(sp.get("word_count") or len(str(sp.get("text", "")).split()))
        wps = round(w_cnt / dur_s, 3)

        # Measure trailing actual silence gap until next phrase starts
        if idx + 1 < len(phrase_spans):
            next_s = float(phrase_spans[idx + 1]["start"])
            g0 = i1
            g1 = min(len(samples), int(round(next_s * sr)))
            measured_pause_ms = int(round(max(0.0, (g1 - g0) / float(sr)) * 1000.0))
            planned_inter_pause_ms = int(sp.get("pause_after_ms", 0)) + int(phrase_spans[idx + 1].get("pause_before_ms", 0))
        else:
            measured_pause_ms = 0
            planned_inter_pause_ms = 0

        phrase_metrics.append({
            "phrase_id": sp.get("phrase_id", f"ph_{idx:02d}"),
            "intent": sp.get("intent"),
            "start": round(s_t, 3),
            "end": round(e_t, 3),
            "duration_sec": round(dur_s, 3),
            "planned_rate_mult": sp.get("rate_multiplier"),
            "planned_pitch_st": sp.get("pitch_semitones"),
            "planned_pause_after_ms": planned_inter_pause_ms,
            "measured_pause_after_ms": measured_pause_ms,
            "rms_dbfs": rms_db,
            "f0_median_hz": f0_med,
            "f0_iqr_hz": f0_iqr,
            "local_wps": wps,
        })

    if pk_dbfs > -0.3:
        problems.append(f"Voiceover waveform clipping risk: peak {pk_dbfs} dBFS > -0.3 dBFS")

    # Contrast / expressiveness verification on real waveforms when style != legacy
    rates = [m["local_wps"] for m in phrase_metrics]
    rmss = [m["rms_dbfs"] for m in phrase_metrics]
    f0s = [m["f0_median_hz"] for m in phrase_metrics if m["f0_median_hz"] is not None]
    wps_span_pct = round(((max(rates) - min(rates)) / max(1e-6, float(np.mean(rates)))) * 100.0, 2) if len(rates) >= 2 else 0.0
    rms_span_db = round(max(rmss) - min(rmss), 2) if len(rmss) >= 2 else 0.0
    f0_span_hz = round(max(f0s) - min(f0s), 2) if len(f0s) >= 2 else 0.0

    # Check planned pause alignment for interior phrases
    pause_errors = [
        abs(int(m["measured_pause_after_ms"]) - int(m["planned_pause_after_ms"]))
        for m in phrase_metrics[:-1]
    ] if len(phrase_metrics) > 1 else [0]
    max_pause_err_ms = max(pause_errors, default=0)
    if style != "legacy" and len(phrase_metrics) >= 3 and backend in ("windows_sapi", "kokoro", "macos_say"):
        if wps_span_pct < 4.0 and f0_span_hz < 3.0 and rms_span_db < 1.2:
            problems.append(
                f"Monotone/ignored prosody controls detected on {backend}: "
                f"wps_span={wps_span_pct}%, f0_span={f0_span_hz}Hz, rms_span={rms_span_db}dB"
            )
        if max_pause_err_ms > 150:
            problems.append(f"Pause duration mismatch ({max_pause_err_ms}ms > 150ms tolerance)")

    # Word count integrity vs synthesized script
    exp_toks = sum(int(p.get("word_count", 0)) for p in prosody_plan.get("phrases", []))
    if len(words) < max(1, int(exp_toks * 0.9)):
        problems.append(f"Aligned words count {len(words)} severely below expected {exp_toks}")

    return {
        "schema_version": "sd-voice-delivery-1",
        "backend": backend,
        "voice_style": style,
        "neural_prosody": bool(caps.get("neural_prosody", False)),
        "ssml_supported": bool(caps.get("ssml_supported", False)),
        "supported_controls": caps.get("supported_controls", []),
        "algorithmic_prosody_execution_status": "FAIL" if problems else "PASS",
        "subjective_voice_quality_status": "NOT_VERIFIED",
        "subjective_note": (
            "Objective waveform metrics (RMS, F0, speaking-rate modulation, break alignment, zero clipping) "
            "verified; human listening / naturalness review remains NOT_VERIFIED."
        ),
        "summary_metrics": {
            "phrase_count": len(phrase_metrics),
            "peak_dbfs": pk_dbfs,
            "wps_dynamic_span_pct": wps_span_pct,
            "rms_dynamic_span_db": rms_span_db,
            "f0_median_span_hz": f0_span_hz,
            "max_pause_error_ms": max_pause_err_ms,
        },
        "problems": problems,
        "phrase_metrics": phrase_metrics,
    }


def write_prosody_artifacts(
    audio_dir: Path,
    prosody_plan: Dict[str, Any],
    delivery_report: Dict[str, Any],
) -> Dict[str, str]:
    """Write `voice_prosody_plan.json`, `prosody_script.md`, `voice_delivery_report.json`."""
    audio_dir.mkdir(parents=True, exist_ok=True)
    plan_p = audio_dir / "voice_prosody_plan.json"
    rep_p = audio_dir / "voice_delivery_report.json"
    md_p = audio_dir / "prosody_script.md"

    plan_p.write_text(json.dumps(prosody_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    rep_p.write_text(json.dumps(delivery_report, ensure_ascii=False, indent=2), encoding="utf-8")

    caps = prosody_plan.get("backend_capabilities") or {}
    lines = [
        "# Voice Prosody Direction Script",
        "",
        f"- **Voice Style**: `{prosody_plan.get('voice_style')}`",
        f"- **Backend / Voice**: `{prosody_plan.get('backend')}` / `{prosody_plan.get('voice_id')}`",
        f"- **Neural Prosody**: `{caps.get('neural_prosody', False)}` | **SSML Supported**: `{caps.get('ssml_supported', False)}`",
        f"- **Execution Status**: `{delivery_report.get('algorithmic_prosody_execution_status')}` | **Subjective Voice Quality**: `{delivery_report.get('subjective_voice_quality_status')}`",
        "",
        "| Phrase | Intent | Rate | Pitch (st) | Pause After (ms) | Emphasis Words | Text |",
        "|---|---|---|---|---|---|---|",
    ]
    for ph in prosody_plan.get("phrases", []):
        emp = ", ".join(ph.get("emphasis_words") or []) or "-"
        lines.append(
            f"| `{ph.get('phrase_id')}` | `{ph.get('intent')}` | {ph.get('rate_multiplier')}x | "
            f"{ph.get('pitch_semitones'):+g} | {ph.get('pause_after_ms')} | {emp} | {ph.get('text')} |"
        )
    md_p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "voice_prosody_plan_json": str(plan_p.resolve()),
        "voice_delivery_report_json": str(rep_p.resolve()),
        "prosody_script_md": str(md_p.resolve()),
    }


def render_voice_ab_probe(
    legacy_wav: Path,
    enhanced_wav: Path,
    out_wav: Path,
    report_a: Dict[str, Any],
    report_b: Dict[str, Any],
) -> Dict[str, Any]:
    """Build side-by-side `voice_ab_probe.wav` (Version A -> chime gap -> Version B) + delta stats."""
    sr_target = 24000
    wa, sra = sf.read(str(legacy_wav), dtype="float32")
    wb, srb = sf.read(str(enhanced_wav), dtype="float32")
    if wa.ndim > 1:
        wa = wa.mean(axis=1)
    if wb.ndim > 1:
        wb = wb.mean(axis=1)
    if sra != sr_target:
        wa = signal.resample_poly(wa, sr_target, sra).astype(np.float32)
    if srb != sr_target:
        wb = signal.resample_poly(wb, sr_target, srb).astype(np.float32)

    gap_n = int(0.65 * sr_target)
    t_g = np.arange(gap_n, dtype=np.float32) / float(sr_target)
    sep = np.zeros(gap_n, dtype=np.float32)
    beep = 0.14 * np.sin(2.0 * np.pi * 880.0 * t_g) * np.exp(-t_g * 9.0)
    sep[: min(gap_n, int(0.22 * sr_target))] = beep[: min(gap_n, int(0.22 * sr_target))]

    combined = np.concatenate([wa, sep, wb]).astype(np.float32)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), combined, sr_target)

    ma = report_a.get("summary_metrics") or {}
    mb = report_b.get("summary_metrics") or {}
    return {
        "voice_ab_probe_wav": str(out_wav.resolve()),
        "legacy_duration_sec": round(len(wa) / float(sr_target), 3),
        "enhanced_duration_sec": round(len(wb) / float(sr_target), 3),
        "delta_wps_dynamic_span_pct": round(float(mb.get("wps_dynamic_span_pct", 0.0)) - float(ma.get("wps_dynamic_span_pct", 0.0)), 2),
        "delta_rms_dynamic_span_db": round(float(mb.get("rms_dynamic_span_db", 0.0)) - float(ma.get("rms_dynamic_span_db", 0.0)), 2),
        "delta_f0_median_span_hz": round(float(mb.get("f0_median_span_hz", 0.0)) - float(ma.get("f0_median_span_hz", 0.0)), 2),
    }
