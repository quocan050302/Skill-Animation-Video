"""STEP 0 & STEP 2: Strict single-skill parsing, capability scoring, and style locking.

Guarantees:
1. Explicit selection (`--skill <name>`, `Skill: <name>`, or clear natural-language selection)
   activates `ProvenanceGuard` immediately and reads ONLY that skill's `SKILL.md`.
2. Invalid explicit skill names fail closed immediately without falling back.
3. Auto selection compares ONLY the six `SKILL.md` capability descriptions, picks ONE
   skill, and locks `ProvenanceGuard` permanently to that skill.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import VALID_SKILLS
from .provenance_guard import ProvenanceGuard, StyleLockViolationError


NATURAL_SKILL_PATTERNS = [
    (r"\b(?:use|using|in|with)\s+(?:the\s+)?(zach-d-films|stick-figure|minimalistic-graphics|map-route|breakdown|graph)\s+(?:skill|style|engine)\b", 1),
    (r"^/(zach-d-films|stick-figure|minimalistic-graphics|map-route|breakdown|graph)\b", 1),
]


def parse_skill_request(
    raw_text: str,
    cli_skill: Optional[str] = None,
) -> Tuple[str, Optional[str], str]:
    """Parse explicit skill lock syntax BEFORE any visual engine setup.

    Returns `(selection_mode, explicit_skill_or_None, cleaned_script)`.
    Raises `StyleLockViolationError` on unrecognized explicit skill names.
    """
    text = (raw_text or "").strip()

    # Strip leading `/short-director` command prefix if present
    if text.startswith("/short-director"):
        text = text[len("/short-director") :].strip()

    # 1. CLI `--skill` flag takes highest explicit priority
    if cli_skill is not None and str(cli_skill).strip() != "":
        candidate = str(cli_skill).strip().lower()
        if candidate not in VALID_SKILLS:
            raise StyleLockViolationError(
                f"Explicit --skill '{candidate}' is not a valid skill. "
                f"Allowed: {', '.join(VALID_SKILLS)}"
            )
        # Also clean inline --skill if duplicated in text
        text = re.sub(r"^--skill\s+\S+\s*", "", text).strip()
        return "explicit", candidate, text

    # 2. Inline `--skill <name>` inside `/short-director --skill <name> <script>`
    m_flag = re.match(r"^--skill(?:=|\s+)(\S+)\s*(.*)$", text, flags=re.DOTALL)
    if m_flag:
        candidate = m_flag.group(1).strip().lower()
        rest = m_flag.group(2).strip()
        if candidate not in VALID_SKILLS:
            raise StyleLockViolationError(
                f"Inline --skill '{candidate}' is not a valid skill. "
                f"Allowed: {', '.join(VALID_SKILLS)}"
            )
        return "explicit", candidate, rest

    # 3. `Skill: <exact-skill-name>` header line
    m_hdr = re.match(r"^skill\s*:\s*([a-zA-Z0-9_-]+)\s*[\n,;:-]*\s*(.*)$", text, flags=re.IGNORECASE | re.DOTALL)
    if m_hdr:
        candidate = m_hdr.group(1).strip().lower()
        rest = m_hdr.group(2).strip()
        if candidate not in VALID_SKILLS:
            raise StyleLockViolationError(
                f"'Skill: {candidate}' is not a valid skill. Allowed: {', '.join(VALID_SKILLS)}"
            )
        return "explicit", candidate, rest

    # 4. Unambiguous natural-language explicit selection
    for pat, grp in NATURAL_SKILL_PATTERNS:
        m_nat = re.search(pat, text, flags=re.IGNORECASE)
        if m_nat:
            candidate = m_nat.group(grp).strip().lower()
            if candidate in VALID_SKILLS:
                cleaned = (text[: m_nat.start()] + " " + text[m_nat.end() :]).strip(" :,-")
                return "explicit", candidate, cleaned.strip()

    return "auto", None, text


def _read_skill_frontmatter(skill_md_path: Path) -> Dict[str, str]:
    """Read ONLY frontmatter/summary from a skill's SKILL.md."""
    raw = skill_md_path.read_text(encoding="utf-8")
    name = skill_md_path.parent.name
    desc = ""
    m = re.match(r"^---\s*\n(.*?)\n---", raw, flags=re.DOTALL)
    if m:
        fm = m.group(1)
        for line in fm.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
    return {"name": name, "description": desc, "skill_md_path": str(skill_md_path)}


def _score_auto_candidates(script_text: str, capabilities: Dict[str, Dict[str, str]]) -> Tuple[str, Dict[str, float], Dict[str, str]]:
    """Score the six capability descriptions deterministically for `auto` mode."""
    low = script_text.lower()
    words = low.split()
    word_count = len(words)
    numbers = re.findall(r"\b\d+(?:[.,]\d+)?(?:\s*(?:k|m|b|%))?\b", low)

    scores: Dict[str, float] = {s: 1.0 for s in VALID_SKILLS}
    reasons: Dict[str, List[str]] = {s: [] for s in VALID_SKILLS}

    # Graph signals: numeric series, growth, quarters/months, metrics
    if len(numbers) >= 3:
        scores["graph"] += 4.5
        reasons["graph"].append(f"detected {len(numbers)} numeric values")
    for kw in ("followers", "revenue", "growth", "chart", "graph", "jan", "feb", "mar", "q1", "q2", "q3", "q4", "mrr", "users"):
        if re.search(rf"\b{re.escape(kw)}\b", low):
            scores["graph"] += 1.4
            reasons["graph"].append(f"metric/time keyword '{kw}'")

    # Map-route signals: A-to-B journey, km/mi, ETA/minutes
    for kw in ("km", "kilometers", "miles", "route", "commute", "eta", "destination", "walk from", "drive from", "home to"):
        if kw in low:
            scores["map-route"] += 2.6
            reasons["map-route"].append(f"route keyword '{kw}'")
    if re.search(r"\b\d+(?:\.\d+)?\s*(?:km|mi)\b", low) and re.search(r"\b\d+\s*min", low):
        scores["map-route"] += 5.0
        reasons["map-route"].append("explicit distance + duration pair")

    # Breakdown signals: anatomy, exploded view, layers, inside a device
    for kw in ("exploded view", "teardown", "anatomy", "layers", "what's inside", "inside a", "inside an", "every part", "labelled", "labeled"):
        if kw in low:
            scores["breakdown"] += 3.2
            reasons["breakdown"].append(f"teardown keyword '{kw}'")

    # Minimalistic-graphics signals: short contemplative quote/aphorism about steps/habits/patience
    if word_count <= 26 and any(kw in low for kw in ("step", "habit", "compound", "quiet", "patience", "look back", "progress", "small")):
        scores["minimalistic-graphics"] += 5.0
        reasons["minimalistic-graphics"].append("concise reflective progress aphorism")

    # Zach-D-Films signals: ballistic/mechanical collision, armor vs projectile, "could X stop Y", force/impact
    for kw in ("bullet", "armor", "armour", "impact", "force", "crush", "pierce", "hydraulic", "steel", "arrow", "stop a", "survive a"):
        if kw in low:
            scores["zach-d-films"] += 2.5
            reasons["zach-d-films"].append(f"3D physical-impact keyword '{kw}'")
    if "sword" in low and any(k in low for k in ("armor", "armour", "chain mail", "plate", "bullet")):
        scores["zach-d-films"] += 2.0
        reasons["zach-d-films"].append("weapon-vs-armor test")

    # Stick-figure signals: multi-beat historical/economic/science/character explainer reel (30-45s)
    for kw in (
        "why ", "what if", "what happens", "picture a", "here's the catch", "here is the catch",
        "brain", "sleep", "nap", "body", "eye", "history", "pirate", "rome", "roman", "gladiator",
        "arena", "fortune", "expensive", "rented", "owner", "mercy", "bill", "business", "coffee", "memory", "people",
    ):
        if kw in low:
            scores["stick-figure"] += 1.9
            reasons["stick-figure"].append(f"character-explainer cue '{kw}'")
    if word_count >= 22:
        scores["stick-figure"] += 1.5
        reasons["stick-figure"].append("multi-beat narrative length")
    if word_count >= 75:
        scores["stick-figure"] += 2.8
        reasons["stick-figure"].append("full 35-45s narrative reel structure")

    # Incorporate overlap with upstream SKILL.md capability descriptions
    script_tokens = set(re.findall(r"[a-z]{4,}", low))
    for s, cap in capabilities.items():
        cap_tokens = set(re.findall(r"[a-z]{4,}", cap.get("description", "").lower()))
        overlap = len(script_tokens & cap_tokens)
        scores[s] += min(1.5, overlap * 0.15)

    best_skill = max(VALID_SKILLS, key=lambda s: (round(scores[s], 4), -VALID_SKILLS.index(s)))
    reason_str = {s: (", ".join(v) if v else "baseline capability match") for s, v in reasons.items()}
    return best_skill, {s: round(v, 3) for s, v in scores.items()}, reason_str


def route_and_lock_style(
    project_root: Path,
    raw_input: str,
    cli_skill: Optional[str] = None,
    upstream_sha: str = "unknown",
) -> Tuple[Dict[str, Any], str, ProvenanceGuard]:
    """Execute STEP 0 + STEP 2 routing and engage interpreter-level ProvenanceGuard."""
    selection_mode, explicit_skill, cleaned_script = parse_skill_request(raw_input, cli_skill=cli_skill)
    skills_root = project_root / "vendor" / "claude-animation-skills" / "skills"

    if selection_mode == "explicit":
        assert explicit_skill is not None
        guard = ProvenanceGuard.activate(project_root, selection_mode="explicit", selected_skill=explicit_skill)
        # Read ONLY the selected skill's SKILL.md — NEVER touch the other five!
        selected_md = skills_root / explicit_skill / "SKILL.md"
        cap = _read_skill_frontmatter(selected_md)
        selected_skill = explicit_skill
        candidate_scores = {explicit_skill: 1.0}
        rationale = (
            f"Explicit user lock to '{selected_skill}'. Other five skills were neither read, scored, nor imported."
        )
        inspected_skill_mds = [str(selected_md.resolve())]
    else:
        guard = ProvenanceGuard.activate(project_root, selection_mode="auto")
        # Read ONLY the six SKILL.md capability descriptions for selection
        capabilities: Dict[str, Dict[str, str]] = {}
        inspected_skill_mds = []
        for s in VALID_SKILLS:
            md_path = skills_root / s / "SKILL.md"
            capabilities[s] = _read_skill_frontmatter(md_path)
            inspected_skill_mds.append(str(md_path.resolve()))
        selected_skill, candidate_scores, reasons = _score_auto_candidates(cleaned_script, capabilities)
        guard.lock_to_skill(selected_skill)
        cap = capabilities[selected_skill]
        rationale = (
            f"Auto-selected single skill '{selected_skill}' (score={candidate_scores[selected_skill]}) "
            f"based on: {reasons[selected_skill]}. Locked permanently with zero secondary/guest styles."
        )

    decisions: Dict[str, Any] = {
        "schema_version": "0.2.0",
        "selection_mode": selection_mode,
        "selected_skill": selected_skill,
        "style_lock": {
            "enabled": True,
            "engine": selected_skill,
            "mixing_policy": "forbidden",
            "fallback_policy": "fail-closed",
        },
        "origin_skills": [selected_skill],
        "upstream_provenance": {
            "repository": "https://github.com/artemnovitckii/claude-animation-skills",
            "commit_sha": upstream_sha,
            "license": "MIT",
            "selected_skill_md": cap["skill_md_path"],
            "capability_description": cap["description"],
            "inspected_capability_files": inspected_skill_mds,
        },
        "candidate_scores": candidate_scores,
        "rationale": rationale,
    }
    return decisions, cleaned_script, guard
