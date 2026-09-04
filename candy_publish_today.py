#!/usr/bin/env python3
r"""
Candy Trivia — safe one-command publisher.

PowerShell:
  python .\candy_publish_today.py --dry-run
  python .\candy_publish_today.py

Rules:
- Uses scheduledAt already stored in examples\auto\post-###.json.
- Never rewrites schedule times.
- Uses today's remaining slots, otherwise the next campaign date.
- Writes .private\candy-publisher-state.json before calling Buffer.
- SENT and PUBLISHING/UNCERTAIN posts are never automatically retried.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_DEFAULT = Path(r"C:\Users\perry\AI\ChatGPT\CandyTrivia-TikTok-Factor")
BRANCH = "feature/three-post-autopilot"
TZ = ZoneInfo("America/Phoenix")
STATE_REL = Path(".private") / "candy-publisher-state.json"
POST_RE = re.compile(r"post-(\d{3})\.json$", re.I)


def banner(s: str) -> None:
    print("\n" + "=" * 72 + f"\n{s}\n" + "=" * 72)


def project_dir() -> Path:
    here = Path.cwd()
    if (here / "package.json").exists() and (here / "src").exists():
        return here
    if PROJECT_DEFAULT.exists():
        return PROJECT_DEFAULT
    raise SystemExit("CandyTrivia-TikTok-Factor project not found.")


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def run(cmd: list[str], cwd: Path, label: str) -> None:
    print(f"\n>>> {label}\n    " + " ".join(cmd))
    rc = subprocess.run(cmd, cwd=str(cwd), shell=False).returncode
    if rc:
        raise SystemExit(f"{label} failed with exit code {rc}.")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def scheduled(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"scheduledAt needs timezone offset: {value}")
    return dt.astimezone(TZ)


def fingerprint(data: dict[str, Any]) -> str:
    body = json.dumps(
        {k: data.get(k) for k in ("q1", "q2", "q3", "caption")},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def video_sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_posts(project: Path) -> list[dict[str, Any]]:
    folder = project / "examples" / "auto"
    if not folder.exists():
        raise SystemExit("Missing examples\\auto. Run the v2.7 generator/audit first.")

    posts = []
    for path in sorted(folder.glob("post-*.json")):
        m = POST_RE.fullmatch(path.name)
        if not m:
            continue
        data = read_json(path)
        num = int(data.get("day", m.group(1)))
        when_raw = data.get("scheduledAt")
        if not isinstance(when_raw, str):
            raise SystemExit(f"Missing scheduledAt: {path}")
        posts.append(
            {
                "num": num,
                "path": path,
                "data": data,
                "when": scheduled(when_raw),
                "fp": fingerprint(data),
            }
        )
    if not posts:
        raise SystemExit("No examples\\auto\\post-###.json files found.")
    return posts


def target_date(posts: list[dict[str, Any]], requested: str | None, now: datetime) -> date:
    days = sorted({p["when"].date() for p in posts})
    if requested:
        try:
            chosen = date.fromisoformat(requested)
        except ValueError as exc:
            raise SystemExit("--date must be YYYY-MM-DD.") from exc
        if chosen not in days:
            raise SystemExit(f"No campaign posts scheduled for {chosen}.")
        return chosen

    if any(p["when"].date() == now.date() and p["when"] > now for p in posts):
        return now.date()

    future = [d for d in days if d > now.date()]
    if future:
        return future[0]

    if now.date() in days:
        return now.date()

    raise SystemExit("No current or future campaign dates remain.")


def load_state(project: Path) -> tuple[Path, dict[str, Any]]:
    path = project / STATE_REL
    state = read_json(path) if path.exists() else {"version": 1, "posts": {}}
    state.setdefault("posts", {})
    return path, state


def legacy_sent(project: Path) -> set[int]:
    rows = []
    for path in (
        project / "out" / "manifest.jsonl",
        project / "out" / "publish-ledger.jsonl",
        project / ".private" / "publish-ledger.jsonl",
    ):
        rows.extend(read_jsonl(path))

    result = set()
    for row in rows:
        try:
            result.add(int(row["day"]))
        except (KeyError, TypeError, ValueError):
            pass
    return result


def set_state(
    path: Path,
    state: dict[str, Any],
    post: dict[str, Any],
    status: str,
    *,
    sha: str | None = None,
    buffer_id: str | None = None,
) -> None:
    key = f"{post['num']:03d}"
    now = datetime.now(TZ).isoformat(timespec="seconds")
    item = dict(state["posts"].get(key, {}))
    item.update(
        {
            "post": post["num"],
            "status": status,
            "scheduledAt": post["when"].isoformat(timespec="seconds"),
            "contentFingerprint": post["fp"],
            "updatedAt": now,
        }
    )
    if status == "PUBLISHING":
        item["attemptedAt"] = now
    if status == "SENT":
        item["completedAt"] = now
    if sha:
        item["videoSha256"] = sha
    if buffer_id:
        item["bufferPostId"] = buffer_id
    state["posts"][key] = item
    write_json_atomic(path, state)


def manifest_buffer_id(project: Path, num: int) -> str | None:
    for row in reversed(read_jsonl(project / "out" / "manifest.jsonl")):
        try:
            if int(row.get("day")) == num:
                value = row.get("bufferPostId")
                return str(value) if value else None
        except (TypeError, ValueError):
            continue
    return None


def verify_video(project: Path, num: int) -> Path:
    path = project / "out" / f"candy-trivia-day-{num:03d}.mp4"
    if not path.exists():
        raise SystemExit(f"Rendered MP4 missing: {path}")
    mb = path.stat().st_size / 1024 / 1024
    if mb < 0.5:
        raise SystemExit(f"Rendered MP4 is suspiciously small: {mb:.2f} MB")
    print(f"Verified {path.name} ({mb:.1f} MB)")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Publish a specific campaign date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project = project_dir()
    now = datetime.now(TZ)

    if not shutil.which("git"):
        raise SystemExit("git not found in PATH.")
    if not (shutil.which("npm") or shutil.which("npm.cmd")):
        raise SystemExit("npm not found in PATH.")

    banner("CANDY TRIVIA — SAFE DAILY PUBLISHER")
    print(f"Project: {project}")
    print(f"Now: {now.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")

    if not args.dry_run:
        banner("1. UPDATE")
        run(["git", "checkout", BRANCH], project, "Checkout branch")
        run(["git", "pull", "--ff-only", "origin", BRANCH], project, "Pull GitHub")
        run([npm(), "run", "typecheck"], project, "TypeScript check")

    posts = load_posts(project)
    chosen = target_date(posts, args.date, now)
    selected = sorted(
        [p for p in posts if p["when"].date() == chosen],
        key=lambda p: p["when"],
    )
    if len(selected) > 3:
        raise SystemExit(f"Safety stop: {len(selected)} posts found for {chosen}; expected <= 3.")

    state_path, state = load_state(project)
    sent_days = legacy_sent(project)
    sent_fps = {
        x.get("contentFingerprint")
        for x in state["posts"].values()
        if isinstance(x, dict) and x.get("status") == "SENT"
    }

    banner(f"2. SAFETY CHECK — {chosen}")
    ready = []
    for post in selected:
        num = post["num"]
        item = state["posts"].get(f"{num:03d}", {})
        status = item.get("status") if isinstance(item, dict) else None

        print(f"Post {num:03d}: {post['when'].strftime('%I:%M %p %Z')}", end=" — ")

        if num in sent_days or status == "SENT":
            print("SKIP, already sent")
        elif status == "PUBLISHING":
            print("BLOCKED, prior result uncertain")
        elif post["fp"] in sent_fps:
            print("BLOCKED, same content already sent")
        elif post["when"] <= now:
            print("SKIP, scheduled time already passed")
        else:
            print("READY")
            ready.append(post)

    if args.dry_run:
        banner("DRY RUN — NOTHING PUBLISHED")
        print("Ready:", [f"{p['num']:03d}" for p in ready])
        return

    if not ready:
        banner("NO NEW POSTS")
        print("Nothing was submitted to Buffer.")
        return

    banner("3. RENDER NEW POSTS")
    videos: dict[int, Path] = {}
    for post in ready:
        num = post["num"]
        rel = post["path"].relative_to(project)
        run([npm(), "run", "render-local", "--", str(rel)], project, f"Render {num:03d}")
        videos[num] = verify_video(project, num)

    banner("4. PUBLISH EXACTLY ONCE")
    published = []
    for post in ready:
        num = post["num"]
        sha = video_sha(videos[num])

        # Critical safety step: save PUBLISHING before Buffer is called.
        # If the outcome becomes ambiguous, reruns block instead of duplicating.
        set_state(state_path, state, post, "PUBLISHING", sha=sha)

        rel = post["path"].relative_to(project)
        try:
            run([npm(), "run", "publish", "--", str(rel)], project, f"Publish {num:03d}")
        except SystemExit:
            print(
                f"\nSAFETY HOLD: Post {num:03d} remains PUBLISHING/UNCERTAIN.\n"
                "Check Buffer/TikTok before changing or retrying it."
            )
            raise

        buffer_id = manifest_buffer_id(project, num)
        set_state(state_path, state, post, "SENT", sha=sha, buffer_id=buffer_id)
        published.append(num)
        print(f"Post {num:03d}: SENT" + (f" | Buffer {buffer_id}" if buffer_id else ""))

    banner("5. ANALYTICS")
    run([npm(), "run", "analytics"], project, "Analytics")

    banner("SUCCESS")
    print("Published/scheduled:", [f"{n:03d}" for n in published])
    print("Safe to rerun: SENT and UNCERTAIN posts will not be resubmitted.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
