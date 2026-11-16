"""STEP 6 & STEP 7: Editorial Timeline Assembler, Captions Sidecar, Grade, Preview 1080p & Final 4K."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List


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
    audio_master_af = "alimiter=limit=0.88:attack=3:release=60,loudnorm=I=-14:TP=-1.5:LRA=9"
    grade_vf = f"eq=contrast={contrast:.3f}:saturation={saturation:.3f}"

    preview_mp4 = run_dir / "preview_1080.mp4"
    final_4k_mp4 = run_dir / "final_4k.mp4"

    if render_info["native_4k"]:
        # Master picture is already genuine native 2160x3840!
        # Encode Final 4K (2160x3840) with subtle cohesive grade + mastered audio
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y",
                "-i", str(silent_master),
                "-i", str(mix_wav),
                "-map", "0:v:0", "-map", "1:a:0",
                "-vf", f"{grade_vf},format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "17",
                "-r", str(fps),
                "-af", audio_master_af,
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
                "-vf", "scale=1080:1920:flags=lanczos,format=yuv420p",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
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
                "-vf", f"scale=1080:1920:flags=lanczos,{grade_vf},format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "17",
                "-r", str(fps),
                "-af", audio_master_af,
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
                "-vf", "scale=2160:3840:flags=lanczos,unsharp=5:5:0.35:5:5:0.0,format=yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
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
