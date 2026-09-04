#!/usr/bin/env python3
"""Safely migrate to the premium branch and recover today's Candy posts.

The script is intentionally local because the Buffer/R2 credentials and the
append-only duplicate-protection history live only in the operator checkout.
It preserves untracked files that would block the branch switch, applies the
approved A/A/B template rotation, moves posts 007-009 into one-hour recovery
slots beginning at or after 7 PM today, performs a Buffer-aware dry run, and
publishes only with --apply. Later campaign dates retain their normal schedule.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


BRANCH = "feature/super-premium-candy-graphics"
REMOTE = "origin"
PHOENIX = ZoneInfo("America/Phoenix")
TODAY_POSTS = (7, 8, 9)
MINIMUM_LEAD = timedelta(minutes=45)
SPACING = timedelta(hours=1)
RECOVERY_START_HOUR = 19
LATEST_SLOT_HOUR = 23
BACKUP_ROOT = Path(".private") / "premium-migration-backups"


class SafeStop(RuntimeError):
    pass


def command_text(command: list[str]) -> str:
    return subprocess.list2cmdline(command)


def run(
    command: list[str],
    cwd: Path,
    *,
    capture: bool = False,
    env: dict[str, str] | None = None,
) -> str:
    print(f"\n> {command_text(command)}", flush=True)
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=capture,
        env=env,
    )
    if result.returncode:
        if capture:
            if result.stdout.strip():
                print(result.stdout.strip())
            if result.stderr.strip():
                print(result.stderr.strip(), file=sys.stderr)
        raise SafeStop(
            f"Command failed with exit code {result.returncode}: {command_text(command)}"
        )
    return result.stdout.strip() if capture else ""


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise SafeStop("Run this from inside CandyTrivia-TikTok-Factor.")
    root = Path(result.stdout.strip()).resolve()
    if not (root / "package.json").exists() or not (root / "src").is_dir():
        raise SafeStop(f"This does not look like the Candy Trivia repository: {root}")
    return root


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def parse_porcelain_z(raw: str) -> tuple[list[str], list[str]]:
    tracked_changes: list[str] = []
    untracked: list[str] = []
    for entry in raw.split("\0"):
        if not entry:
            continue
        status = entry[:2]
        path = entry[3:]
        if status == "??":
            untracked.append(path)
        elif status != "!!":
            tracked_changes.append(f"{status} {path}")
    return tracked_changes, untracked


def backup_checkout_conflicts(root: Path) -> Path | None:
    status = run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        root,
        capture=True,
    )
    tracked_changes, untracked = parse_porcelain_z(status)
    if tracked_changes:
        print("\nTracked user changes were found:")
        for item in tracked_changes:
            print(f"  {item}")
        raise SafeStop(
            "Tracked changes were not moved or stashed. Commit them or ask for review first."
        )

    remote_paths = set(
        run(
            ["git", "ls-tree", "-r", "--name-only", f"{REMOTE}/{BRANCH}"],
            root,
            capture=True,
        ).splitlines()
    )
    conflicts = sorted(path for path in untracked if path.replace("\\", "/") in remote_paths)
    if not conflicts:
        return None

    stamp = datetime.now(PHOENIX).strftime("%Y%m%d-%H%M%S")
    backup = root / BACKUP_ROOT / stamp
    print(f"\nPreserving {len(conflicts)} checkout-conflicting untracked file(s) in:")
    print(f"  {backup}")
    for relative in conflicts:
        source = root / relative
        destination = backup / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        print(f"  preserved: {relative}")
    return backup


def switch_to_premium(root: Path) -> Path | None:
    run(["git", "fetch", REMOTE, BRANCH], root)
    backup = backup_checkout_conflicts(root)
    local_exists = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{BRANCH}"],
        cwd=root,
        check=False,
    ).returncode == 0
    if local_exists:
        run(["git", "switch", BRANCH], root)
    else:
        run(["git", "switch", "--track", "-c", BRANCH, f"{REMOTE}/{BRANCH}"], root)
    run(["git", "pull", "--ff-only", REMOTE, BRANCH], root)
    return backup


def round_up_quarter(value: datetime) -> datetime:
    value = value.replace(second=0, microsecond=0)
    remainder = value.minute % 15
    if remainder:
        value += timedelta(minutes=15 - remainder)
    return value


def plan_slots(now: datetime) -> list[datetime]:
    requested_start = now.replace(
        hour=RECOVERY_START_HOUR,
        minute=0,
        second=0,
        microsecond=0,
    )
    first = max(requested_start, round_up_quarter(now + MINIMUM_LEAD))
    slots = [first + index * SPACING for index in range(len(TODAY_POSTS))]
    if any(slot.date() != now.date() for slot in slots):
        raise SafeStop(
            "There is no longer enough time to place three well-spaced posts today. "
            "Nothing was scheduled. Use tomorrow's campaign instead."
        )
    latest = now.replace(hour=LATEST_SLOT_HOUR, minute=59, second=59, microsecond=0)
    if slots[-1] > latest:
        raise SafeStop(
            "The final recovery slot would be after 11:59 PM Phoenix time. "
            "Nothing was scheduled."
        )
    return slots


def apply_rotation_and_slots(root: Path, slots: list[datetime]) -> list[Path]:
    campaign = root / "examples" / "auto"
    files = sorted(campaign.glob("post-*.json"))
    if len(files) != 42:
        raise SafeStop(f"Expected 42 campaign files on the premium branch; found {len(files)}.")

    changed: list[Path] = []
    slots_by_day = dict(zip(TODAY_POSTS, slots, strict=True))
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        day = int(data.get("day", path.stem.removeprefix("post-")))
        template = "B" if day % 3 == 0 else "A"
        dirty = data.get("visualTemplate") != template
        data["visualTemplate"] = template
        if day in slots_by_day:
            scheduled_at = slots_by_day[day].isoformat(timespec="seconds")
            dirty = dirty or data.get("scheduledAt") != scheduled_at
            data["scheduledAt"] = scheduled_at
        if dirty:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            changed.append(path)
    return changed


def commit_campaign_plan(root: Path, changed: list[Path]) -> str:
    if not changed:
        return run(["git", "rev-parse", "HEAD"], root, capture=True)
    run(["git", "add", "--", "examples/auto"], root)
    run(["git", "diff", "--cached", "--check"], root)
    staged = run(["git", "diff", "--cached", "--name-only"], root, capture=True)
    if any(not line.startswith("examples/auto/post-") for line in staged.splitlines()):
        raise SafeStop("Safety stop: a non-campaign file was staged.")
    run(
        ["git", "commit", "-m", "Apply AAB rotation and recover missed Candy posts"],
        root,
    )
    sha = run(["git", "rev-parse", "HEAD"], root, capture=True)
    run(["git", "push", REMOTE, f"HEAD:refs/heads/{BRANCH}"], root)
    return sha


def publishing_environment() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "OPENAI_IMAGES_ENABLED": "0",
            "TTS_ENABLED": "1",
            "TTS_VOICE": "en-US-AvaNeural",
            "TTS_RATE": "+8%",
            "TTS_PITCH": "+0Hz",
            "CANDY_PUBLISHING_DISABLED": "0",
        }
    )
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely schedule today's three premium Candy Trivia posts."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="After the mandatory Buffer-aware dry run, render and schedule the posts.",
    )
    args = parser.parse_args()

    root = repo_root()
    if not (root / ".env").exists():
        raise SafeStop("Local .env is missing; Buffer and R2 credentials were not available.")

    now = datetime.now(PHOENIX)
    slots = plan_slots(now)
    print("\nCandy Premium recovery plan (America/Phoenix):")
    for day, slot in zip(TODAY_POSTS, slots, strict=True):
        template = "B" if day % 3 == 0 else "A"
        print(f"  Post {day:03d}: {slot:%Y-%m-%d %I:%M %p} | Template {template}")
    print("  Recovery spacing: 1 hour | minimum initial lead: 45 minutes")
    print("  Posts 010-042 retain their normal 9 AM / 3 PM / 7 PM schedule.")

    backup = switch_to_premium(root)
    changed = apply_rotation_and_slots(root, slots)
    sha = commit_campaign_plan(root, changed)
    print(f"\nPremium campaign commit: {sha}")
    if backup:
        print(f"Original conflicting files remain preserved at: {backup}")

    env = publishing_environment()
    run([npm_command(), "ci"], root, env=env)
    run([npm_command(), "run", "typecheck"], root, env=env)
    run([npm_command(), "run", "audit-content"], root, env=env)

    campaign_date = slots[0].date().isoformat()
    print("\nMANDATORY BUFFER-AWARE DRY RUN")
    run(
        [sys.executable, "candy_autopilot.py", "--dry-run", "--date", campaign_date],
        root,
        env=env,
    )

    if not args.apply:
        print("\nDRY RUN COMPLETE. Nothing was rendered, uploaded, or scheduled.")
        print("Run this script again with --apply only after reviewing the output.")
        return 0

    print("\nLIVE MODE AUTHORIZED BY --apply")
    run(
        [
            sys.executable,
            "candy_autopilot.py",
            "--skip-pull",
            "--date",
            campaign_date,
        ],
        root,
        env=env,
    )
    print("\nSUCCESS: the eligible premium posts were submitted through the existing safe publisher.")
    print("Do not run another publisher from a different checkout.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafeStop as exc:
        print(f"\nSTOPPED SAFELY: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nCancelled. Check Buffer before retrying if cancellation occurred during live mode.")
        raise SystemExit(130)
