"""STEP 6 & STEP 7: Editorial Timeline Assembler, Captions Sidecar, Grade, Preview 1080p & Final 4K."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def _fmt_srt_ts(sec: float) -> str:
    ms_total = max(0, int(round(sec * 1000)))
    hh = ms_total // 3_600_000
    mm = (ms_total % 3_600_000) // 60_000
    ss = (ms_total % 60_000) // 1000
    ms = ms_total % 1000
    return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"


def write_srt_captions(words: List[Dict[str, Any]], out_srt: Path, max_words: int = 3) -> Path:
    """Export frame-aligned `.srt` subtitle track matching on-screen word timings."""
    chunks: List[Dict[str, Any]] = []
    cur: List[Dict[str, Any]] = []
    for i, w in enumerate(words):
        cur.append(w)
        punct = str(w["w"]).endswith((".", ",", "?", "!", ";", ":"))
        if len(cur) >= max_words or punct or i == len(words) - 1:
            chunks.append({
                "s": float(cur[0]["s"]),
                "e": float(cur[-1]["e"]) + 0.15,
                "text": " ".join(str(x["w"]) for x in cur),
            })
            cur = []
    for idx in range(len(chunks) - 1):
        if chunks[idx]["e"] > chunks[idx + 1]["s"]:
            chunks[idx]["e"] = chunks[idx + 1]["s"]

    lines: List[str] = []
    for i, ch in enumerate(chunks, start=1):
        lines.append(str(i))
        lines.append(f"{_fmt_srt_ts(ch['s'])} --> {_fmt_srt_ts(ch['e'])}")
        lines.append(ch["text"])
        lines.append("")
    out_srt.write_text("\n".join(lines), encoding="utf-8")
    return out_srt


def build_contact_sheet(video_mp4: Path, out_jpg: Path, cols: int = 6) -> Path:
    """Render a 6-panel contact sheet with Instagram/Reels 9:16 safe-zone overlay."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video_mp4)],
        capture_output=True,
        text=True,
        check=True,
    )
    dur = max(0.5, float(r.stdout.strip()))
    tw, th = 270, 480
    k = tw / 1080.0
    draw = (
        f"drawbox=x={int(100 * k)}:y={int(220 * k)}:w={int(880 * k)}:"
        f"h={int(1280 * k)}:color=red@0.75:t=2"
    )
    rate = cols / dur
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-i", str(video_mp4),
            "-vf", f"fps={rate:.5f},scale={tw}:{th},{draw},tile={cols}x1",
            "-frames:v", "1",
            str(out_jpg),
        ],
        check=True,
    )
    return out_jpg


def assemble_preview_and_final(
    run_dir: Path,
    storyboard: Dict[str, Any],
    parsed_script: Dict[str, Any],
    render_info: Dict[str, Any],
    audio_info: Dict[str, Any],
) -> Dict[str, Any]:
    """Assemble shot clips + mixed/ducked audio + loudness master into `preview_1080.mp4` and `final_4k.mp4`."""
    shots_info = render_info["shots"]
    fps = int(storyboard["fps"])
    grade_cfg = storyboard.get("style_adapter_params", {}).get("color_grading", {})
    contrast = float(grade_cfg.get("contrast", 1.02))
    saturation = float(grade_cfg.get("saturation", 1.02))

    # 1. Export sidecar SRT captions
    srt_path = write_srt_captions(parsed_script["voice"]["words"], run_dir / "captions.srt")

    # 2. Concatenate frame-accurate shot segments losslessly into master silent picture
    concat_txt = run_dir / "shots" / "concat_list.txt"
    concat_lines = [f"file '{Path(s['path']).resolve()}'" for s in shots_info]
    concat_txt.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")

    silent_master = run_dir / "shots" / "timeline_silent.mp4"
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            str(silent_master),
        ],
        check=True,
    )

    mix_wav = Path(audio_info["mix_wav_path"])
    af_args = [] if audio_info.get("already_mastered") else [
        "-af", "alimiter=limit=0.88:attack=3:release=60,loudnorm=I=-14:TP=-1.5:LRA=9"
    ]
    grade_vf = f"eq=contrast={contrast:.3f}:saturation={saturation:.3f}"

    preview_mp4 = run_dir / "preview_1080.mp4"
    final_4k_mp4 = run_dir / "final_4k.mp4"

    if render_info["native_4k"]:
        # Master picture is already genuine native 2160x3840!
        # Encode Final 4K (2160x3840) with subtle cohesive grade + single-pass mastered audio
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(silent_master),
                "-i", str(mix_wav),
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", f"{grade_vf},scale=out_range=tv,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-color_range", "tv",
                "-r", str(fps),
                *af_args,
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-shortest", "-movflags", "+faststart",
                str(final_4k_mp4),
            ],
            check=True,
        )
        # Supersample downscale to crisp 1080x1920 preview
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(final_4k_mp4),
                "-map", "0:v:0", "-map", "0:a:0",
                "-vf", "scale=1080:1920:flags=lanczos:out_range=tv,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-color_range", "tv",
                "-r", str(fps),
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(preview_mp4),
            ],
            check=True,
        )
    else:
        # Master picture is 1080x1920 -> build Preview 1080p first, then Lanczos upscale to 2160x3840 (explicitly labeled!)
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(silent_master),
                "-i", str(mix_wav),
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", f"scale=1080:1920:flags=lanczos:out_range=tv,{grade_vf},format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p", "-color_range", "tv",
                "-r", str(fps),
                *af_args,
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-shortest", "-movflags", "+faststart",
                str(preview_mp4),
            ],
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(preview_mp4),
                "-map", "0:v:0", "-map", "0:a:0",
                "-vf", "scale=2160:3840:flags=lanczos:out_range=tv,unsharp=5:5:0.35:5:5:0.0,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-color_range", "tv",
                "-r", str(fps),
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(final_4k_mp4),
            ],
            check=True,
        )

    # Remove intermediate silent concat duplicate inside owned shots/ folder to conserve disk
    silent_master.unlink(missing_ok=True)

    sheet_jpg = build_contact_sheet(preview_mp4, run_dir / "contact_sheet.jpg", cols=min(6, max(4, len(shots_info))))

    return {
        "preview_1080_mp4": str(preview_mp4.resolve()),
        "final_4k_mp4": str(final_4k_mp4.resolve()),
        "captions_srt": str(srt_path.resolve()),
        "contact_sheet_jpg": str(sheet_jpg.resolve()),
        "native_4k": render_info["native_4k"],
        "delivery_4k_declaration": render_info["delivery_4k_declaration"],
    }


def compute_video_stream_digest(mp4_path: Path) -> str:
    """Compute MD5 digest over exact demuxed compressed video stream packets (`-c:v copy -f md5`)."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(mp4_path), "-map", "0:v:0", "-c:v", "copy", "-f", "md5", "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = r.stdout.strip()
    if "=" in out:
        return out.split("=", 1)[1].strip()
    return out


def remix_existing_video_audio(
    run_dir: Path,
    storyboard: Dict[str, Any],
    audio_info: Dict[str, Any],
    preserve_original_files: bool = False,
    verify_candidate_fn: Optional[Callable[[Path, Path], Tuple[bool, str]]] = None,
) -> Dict[str, Any]:
    """Lossless `-c:v copy` audio-only remux into verified existing 1080p/4K MP4s.

    - Verifies visual lock & picture provenance BEFORE reading MP4s.
    - Guarantees identical demuxed video packets (MD5 parity before & after mux).
    - Stages in owned `run_dir/tmp/*.partial.mp4` and never overwrites targets on QC failure.
    """
    sd_path = run_dir / "style_decisions.json"
    audit_path = run_dir / "style_lock_audit.json"
    if not sd_path.exists() or not audit_path.exists():
        raise RuntimeError(f"Cannot run --audio-only remux: missing style provenance files in {run_dir}")

    sd = json.loads(sd_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("status") != "PASS":
        raise RuntimeError(f"Refusing --audio-only remux: prior style_lock_audit status={audit.get('status')!r}")
    if sd.get("selected_skill") != storyboard.get("selected_skill"):
        raise RuntimeError(
            f"Visual skill mismatch during --audio-only remux: existing={sd.get('selected_skill')!r} "
            f"vs requested={storyboard.get('selected_skill')!r}"
        )

    mix_wav = Path(audio_info["mix_wav_path"])
    if not mix_wav.exists() or mix_wav.stat().st_size < 44:
        raise RuntimeError(f"Cannot remux missing/empty mix.wav: {mix_wav}")

    src_preview = run_dir / "preview_1080.mp4"
    src_4k = run_dir / "final_4k.mp4"
    if not src_4k.exists() or not src_preview.exists():
        raise RuntimeError(f"Cannot run --audio-only remux: existing MP4 deliverables missing in {run_dir}")

    tmp_dir = run_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    af_args = [] if audio_info.get("already_mastered") else [
        "-af", "alimiter=limit=0.88:attack=3:release=60,loudnorm=I=-14:TP=-1.5:LRA=9"
    ]

    orig_digest_4k = compute_video_stream_digest(src_4k)
    orig_digest_prev = compute_video_stream_digest(src_preview)

    part_4k = tmp_dir / "final_4k.partial.mp4"
    part_prev = tmp_dir / "preview_1080.partial.mp4"

    try:
        for src_v, dst_part in ((src_4k, part_4k), (src_preview, part_prev)):
            subprocess.run(
                [
                    "ffmpeg", "-v", "error", "-y",
                    "-i", str(src_v),
                    "-i", str(mix_wav),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy",
                    *af_args,
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart",
                    str(dst_part),
                ],
                check=True,
            )

        new_digest_4k = compute_video_stream_digest(part_4k)
        new_digest_prev = compute_video_stream_digest(part_prev)
        if new_digest_4k != orig_digest_4k or new_digest_prev != orig_digest_prev:
            raise RuntimeError(
                f"Audio-only remux violated video packet invariance! "
                f"4K {orig_digest_4k}->{new_digest_4k}, preview {orig_digest_prev}->{new_digest_prev}"
            )

        if verify_candidate_fn is not None:
            ok_qc, qc_err = verify_candidate_fn(part_prev, part_4k)
            if not ok_qc:
                raise RuntimeError(f"Remuxed candidate failed QC gate (originals untouched): {qc_err}")

        out_4k = (run_dir / "final_4k_remixed.mp4") if preserve_original_files else src_4k
        out_prev = (run_dir / "preview_1080_remixed.mp4") if preserve_original_files else src_preview
        os.replace(part_4k, out_4k)
        os.replace(part_prev, out_prev)

        return {
            "preview_1080_mp4": str(out_prev.resolve()),
            "final_4k_mp4": str(out_4k.resolve()),
            "video_packet_md5_4k": new_digest_4k,
            "video_packet_md5_preview": new_digest_prev,
            "video_packets_unchanged": True,
            "preserved_originals": preserve_original_files,
        }
    finally:
        part_4k.unlink(missing_ok=True)
        part_prev.unlink(missing_ok=True)
        if tmp_dir.exists() and not any(tmp_dir.iterdir()):
            shutil.rmtree(tmp_dir, ignore_errors=True)
