#!/usr/bin/env python3
"""Safe, one-command Candy Trivia A/B production validation.

This runner intentionally has no publishing implementation. It typechecks, audits
content, renders the approved A/A/B production candidates, validates the media,
extracts QA frames, and writes reports suitable for a GitHub Actions artifact.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out" / "validation"
SAMPLE_DEFAULT = ROOT / "examples" / "day-001.json"
CAMPAIGN_GLOB_DEFAULT = str(ROOT / "examples" / "auto" / "post-*.json")
APPROVED_TEMPLATES = ("A", "B")
ROTATION = ("A", "A", "B")
QA_TIMES = (1.0, 3.0, 9.0, 15.5, 18.0, 22.5, 27.0, 32.6)
EXPECTED_CAMPAIGN_COUNT = 42
EXPECTED_DURATION = 33.6
NARRATION_WINDOWS = {
    "voice-q1.mp3": 6.02,
    "voice-a1.mp3": 2.50,
    "voice-q2.mp3": 6.02,
    "voice-a2.mp3": 2.50,
    "voice-q3.mp3": 6.02,
    "voice-cta.mp3": 3.88,
}


class ValidationError(RuntimeError):
    """Raised when a production gate fails."""


@dataclass(frozen=True)
class MediaResult:
    template: str
    path: str
    size_bytes: int
    duration_seconds: float
    width: int
    height: int
    frame_rate: float
    video_codec: str
    audio_codec: str
    srt_path: str
    srt_size_bytes: int


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def command_text(command: Sequence[str]) -> str:
    return " ".join(f'"{part}"' if " " in part else part for part in command)


def run(command: Sequence[str], *, env: dict[str, str] | None = None) -> None:
    print(f"\n> {command_text(command)}", flush=True)
    completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
    if completed.returncode != 0:
        raise ValidationError(
            f"Command failed with exit code {completed.returncode}: {command_text(command)}"
        )


def captured(command: Sequence[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise ValidationError(
            f"Command failed with exit code {completed.returncode}: {command_text(command)}\n"
            f"{completed.stderr.strip()}"
        )
    return completed.stdout


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise ValidationError(f"Required command is not installed or not on PATH: {name}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ffprobe(path: Path) -> dict[str, Any]:
    return json.loads(
        captured(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )


def stream_by_type(probe: dict[str, Any], codec_type: str) -> dict[str, Any]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == codec_type:
            return stream
    raise ValidationError(f"Rendered MP4 has no {codec_type} stream")


def parse_rate(value: str) -> float:
    numerator, denominator = value.split("/", 1)
    return float(numerator) / float(denominator)


def validate_media(template: str, video: Path, srt: Path) -> MediaResult:
    if not video.is_file() or video.stat().st_size < 1_000_000:
        raise ValidationError(f"Template {template} MP4 is missing or unexpectedly small: {video}")
    if not srt.is_file() or srt.stat().st_size < 100:
        raise ValidationError(f"Template {template} SRT is missing or unexpectedly small: {srt}")

    probe = ffprobe(video)
    video_stream = stream_by_type(probe, "video")
    audio_stream = stream_by_type(probe, "audio")
    duration = float(probe["format"]["duration"])
    rate = parse_rate(video_stream.get("avg_frame_rate") or video_stream["r_frame_rate"])

    checks = {
        "width": int(video_stream["width"]) == 1080,
        "height": int(video_stream["height"]) == 1920,
        "frame rate": abs(rate - 30.0) < 0.01,
        "video codec": video_stream["codec_name"] == "h264",
        "audio codec": audio_stream["codec_name"] == "aac",
        "duration": abs(duration - EXPECTED_DURATION) < 0.25,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise ValidationError(f"Template {template} media checks failed: {', '.join(failures)}")

    run(["ffmpeg", "-v", "error", "-i", str(video), "-f", "null", "-"])
    return MediaResult(
        template=template,
        path=str(video.relative_to(ROOT)),
        size_bytes=video.stat().st_size,
        duration_seconds=duration,
        width=int(video_stream["width"]),
        height=int(video_stream["height"]),
        frame_rate=rate,
        video_codec=video_stream["codec_name"],
        audio_codec=audio_stream["codec_name"],
        srt_path=str(srt.relative_to(ROOT)),
        srt_size_bytes=srt.stat().st_size,
    )


def extract_qa_frames(template: str, video: Path) -> list[str]:
    frame_dir = OUT / "qa-frames" / f"template-{template.lower()}"
    frame_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    for seconds in QA_TIMES:
        output = frame_dir / f"{seconds:04.1f}s.png"
        run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-ss",
                str(seconds),
                "-i",
                str(video),
                "-frames:v",
                "1",
                str(output),
            ]
        )
        if output.stat().st_size < 10_000:
            raise ValidationError(f"QA frame is unexpectedly small: {output}")
        outputs.append(str(output.relative_to(ROOT)))
    return outputs


def voice_directory(day: int) -> Path:
    return ROOT / "public" / "generated" / f"day-{day:03d}"


def validate_narration(day: int) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    results: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for filename, available in NARRATION_WINDOWS.items():
        clip = voice_directory(day) / filename
        if not clip.is_file() or clip.stat().st_size < 512:
            raise ValidationError(f"Neural narration clip is missing or invalid: {clip}")
        duration = float(ffprobe(clip)["format"]["duration"])
        margin = available - duration
        if margin < 0:
            raise ValidationError(
                f"Narration cutoff risk for {filename}: {duration:.3f}s audio in {available:.3f}s window"
            )
        hashes[filename] = sha256(clip)
        results[filename] = {
            "duration_seconds": round(duration, 3),
            "available_seconds": available,
            "safety_margin_seconds": round(margin, 3),
        }
    return results, hashes


def rotation_plan(campaign_files: list[Path]) -> list[dict[str, Any]]:
    if campaign_files:
        rows = []
        for index, path in enumerate(campaign_files):
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows.append(
                {
                    "file": str(path.relative_to(ROOT)),
                    "day": payload.get("day"),
                    "postId": payload.get("postId"),
                    "visualTemplate": ROTATION[index % len(ROTATION)],
                }
            )
        return rows
    return [
        {
            "file": f"examples/auto/post-{index:03d}.json",
            "day": index,
            "postId": f"{index:03d}",
            "visualTemplate": ROTATION[(index - 1) % len(ROTATION)],
        }
        for index in range(1, EXPECTED_CAMPAIGN_COUNT + 1)
    ]


def write_reports(report: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "validation-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "template-rotation-plan.json").write_text(
        json.dumps(report["rotation_plan"], indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# Candy Trivia production validation",
        "",
        f"- Overall result: **{report['status']}**",
        f"- Paid image API: **{report['paid_image_api']}**",
        f"- Publishing: **{report['publishing']}**",
        f"- Campaign files found: **{report['campaign']['found']}**",
        f"- Campaign audit: **{report['campaign']['audit']}**",
        f"- Rotation: **A → A → B** ({report['rotation_counts']['A']} A / {report['rotation_counts']['B']} B)",
        "",
        "| Template | Resolution | FPS | Codecs | Duration | Bytes |",
        "|---|---:|---:|---|---:|---:|",
    ]
    for media in report["media"]:
        lines.append(
            f"| {media['template']} | {media['width']}×{media['height']} | "
            f"{media['frame_rate']:.2f} | {media['video_codec']}/{media['audio_codec']} | "
            f"{media['duration_seconds']:.3f}s | {media['size_bytes']:,} |"
        )
    lines.extend(
        [
            "",
            "Both approved templates use byte-identical neural narration clips.",
            "The runner contains no R2 upload, Buffer, TikTok, scheduling, or publishing step.",
            "",
        ]
    )
    markdown = "\n".join(lines)
    (OUT / "validation-report.md").write_text(markdown, encoding="utf-8")

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(markdown)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render and validate approved Candy Trivia Templates A and B without publishing."
    )
    parser.add_argument("--sample", default=str(SAMPLE_DEFAULT))
    parser.add_argument("--campaign-glob", default=CAMPAIGN_GLOB_DEFAULT)
    parser.add_argument("--expected-campaign-count", type=int, default=EXPECTED_CAMPAIGN_COUNT)
    parser.add_argument("--require-campaign", action="store_true")
    parser.add_argument("--install", action="store_true", help="Run npm ci before validation.")
    parser.add_argument("--skip-render", action="store_true", help="Run audit/plan checks only.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    sample = Path(args.sample).resolve()
    if not sample.is_file():
        raise ValidationError(f"Sample JSON does not exist: {sample}")

    require_tool(npm_command())
    campaign_files = [Path(name).resolve() for name in sorted(glob.glob(args.campaign_glob))]
    if campaign_files and len(campaign_files) != args.expected_campaign_count:
        raise ValidationError(
            f"Expected {args.expected_campaign_count} campaign JSON files, found {len(campaign_files)}"
        )
    if args.require_campaign and len(campaign_files) != args.expected_campaign_count:
        raise ValidationError(
            f"The complete campaign is required but only {len(campaign_files)} files were found. "
            "Add the existing examples/auto/post-*.json files; do not regenerate them."
        )

    safe_env = os.environ.copy()
    safe_env.update(
        {
            "OPENAI_IMAGES_ENABLED": "0",
            "TTS_ENABLED": "1",
            "TTS_VOICE": "en-US-AvaNeural",
            "TTS_RATE": "+8%",
            "TTS_PITCH": "+0Hz",
            "CANDY_PUBLISHING_DISABLED": "1",
        }
    )

    OUT.mkdir(parents=True, exist_ok=True)
    if args.install:
        run([npm_command(), "ci"], env=safe_env)
    run([npm_command(), "run", "typecheck"], env=safe_env)
    audit_files = campaign_files or [sample]
    run(
        [npm_command(), "run", "audit-content", "--", *[str(path) for path in audit_files]],
        env=safe_env,
    )

    plan = rotation_plan(campaign_files)
    counts = {template: sum(row["visualTemplate"] == template for row in plan) for template in APPROVED_TEMPLATES}
    report: dict[str, Any] = {
        "status": "PASS",
        "paid_image_api": "DISABLED",
        "publishing": "DISABLED",
        "campaign": {
            "found": len(campaign_files),
            "expected": args.expected_campaign_count,
            "audit": "PASS" if campaign_files else "SAMPLE_ONLY_CAMPAIGN_FILES_NOT_IN_CHECKOUT",
        },
        "rotation_counts": counts,
        "rotation_plan": plan,
        "media": [],
        "narration": {},
        "qa_frames": {},
    }

    if not args.skip_render:
        require_tool("ffmpeg")
        require_tool("ffprobe")
        sample_payload = json.loads(sample.read_text(encoding="utf-8"))
        day = int(sample_payload["day"])
        narration_hashes: dict[str, dict[str, str]] = {}

        private_root = ROOT / ".private"
        private_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="candy-validation-", dir=private_root) as temporary:
            temporary_dir = Path(temporary)
            for template in APPROVED_TEMPLATES:
                payload = dict(sample_payload)
                payload["visualTemplate"] = template
                input_path = temporary_dir / f"template-{template.lower()}.json"
                input_path.write_text(json.dumps(payload), encoding="utf-8")
                run([npm_command(), "run", "render-local", "--", str(input_path)], env=safe_env)

                rendered = ROOT / "out" / f"candy-trivia-day-{day:03d}.mp4"
                rendered_srt = ROOT / "out" / f"candy-trivia-day-{day:03d}.srt"
                target = OUT / f"template-{template.lower()}-production.mp4"
                target_srt = OUT / f"template-{template.lower()}.srt"
                shutil.copy2(rendered, target)
                shutil.copy2(rendered_srt, target_srt)

                narration, hashes = validate_narration(day)
                narration_hashes[template] = hashes
                report["narration"] = narration
                media = validate_media(template, target, target_srt)
                report["media"].append(asdict(media))
                report["qa_frames"][template] = extract_qa_frames(template, target)

        if narration_hashes["A"] != narration_hashes["B"]:
            raise ValidationError("Templates A and B did not use byte-identical narration clips")
        report["narration_sha256"] = narration_hashes["A"]

    write_reports(report)
    print(f"\nPASS: production validation artifacts written to {OUT}")
    if not campaign_files:
        print(
            "NOTICE: GitHub checkout has no examples/auto/post-*.json files. "
            "Sample audit passed; the 42-post audit remains pending until the existing campaign files are added."
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValidationError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        raise SystemExit(1)
