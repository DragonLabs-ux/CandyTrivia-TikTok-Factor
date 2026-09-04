#!/usr/bin/env python3
r"""
Candy Trivia — ALL-IN-ONE safe autopilot.

This is the only script the operator needs to run.

PowerShell:
  python .\candy_autopilot.py --dry-run
  python .\candy_autopilot.py

Normal run:
1. Updates the GitHub branch.
2. Runs TypeScript typecheck.
3. Audits generated trivia for repeated questions.
4. Checks Buffer for duplicate scheduled copies and deletes ONLY safe scheduled duplicates.
5. Selects the correct campaign date.
6. Skips SENT / UNCERTAIN / past-due posts.
7. Renders only new posts.
8. Marks each post PUBLISHING before Buffer is called.
9. Publishes exactly once and records Buffer IDs.
10. Runs analytics.

Safety:
- Sent TikTok posts are never deleted.
- Unknown Buffer states are never deleted.
- PUBLISHING/UNCERTAIN posts are never automatically retried.
- A failed/ambiguous publish remains blocked until manually verified.
- Dry-run never renders, publishes, or deletes.
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
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PROJECT_DEFAULT = Path(r"C:\Users\perry\AI\ChatGPT\CandyTrivia-TikTok-Factor")
BRANCH = "feature/super-premium-candy-graphics"
TZ = ZoneInfo("America/Phoenix")
STATE_REL = Path(".private") / "candy-publisher-state.json"
POST_RE = re.compile(r"post-(\d{3})\.json$", re.I)
BUFFER_API = "https://api.buffer.com"


def banner(text: str) -> None:
    print("\n" + "=" * 72 + f"\n{text}\n" + "=" * 72)


def project_dir() -> Path:
    here = Path.cwd()
    if (here / "package.json").exists() and (here / "src").exists():
        return here
    if PROJECT_DEFAULT.exists():
        return PROJECT_DEFAULT
    raise SystemExit("CandyTrivia-TikTok-Factor project not found.")


def npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def run(cmd: list[str], cwd: Path, label: str, *, fatal: bool = True) -> bool:
    print(f"\n>>> {label}\n    " + " ".join(cmd))
    rc = subprocess.run(cmd, cwd=str(cwd), shell=False).returncode
    if rc and fatal:
        raise SystemExit(f"{label} failed with exit code {rc}.")
    if rc:
        print(f"WARNING: {label} exited with code {rc}.")
        return False
    return True


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
    rows: list[dict[str, Any]] = []
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


def load_env_file(project: Path) -> None:
    env_file = project / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def scheduled(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit(f"scheduledAt needs timezone offset: {value}")
    return dt.astimezone(TZ)


def fingerprint(data: dict[str, Any]) -> str:
    body = json.dumps(
        {key: data.get(key) for key in ("q1", "q2", "q3", "caption")},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def video_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_posts(project: Path) -> list[dict[str, Any]]:
    folder = project / "examples" / "auto"
    if not folder.exists():
        raise SystemExit(r"Missing examples\auto. Run the v2.7 generator first.")

    posts: list[dict[str, Any]] = []
    for path in sorted(folder.glob("post-*.json")):
        match = POST_RE.fullmatch(path.name)
        if not match:
            continue
        data = read_json(path)
        num = int(data.get("day", match.group(1)))
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
        raise SystemExit(r"No examples\auto\post-###.json files found.")
    return posts


def choose_target_date(posts: list[dict[str, Any]], requested: str | None, now: datetime) -> date:
    campaign_days = sorted({post["when"].date() for post in posts})

    if requested:
        try:
            chosen = date.fromisoformat(requested)
        except ValueError as exc:
            raise SystemExit("--date must be YYYY-MM-DD.") from exc
        if chosen not in campaign_days:
            raise SystemExit(f"No campaign posts scheduled for {chosen}.")
        return chosen

    if any(post["when"].date() == now.date() and post["when"] > now for post in posts):
        return now.date()

    future = [day for day in campaign_days if day > now.date()]
    if future:
        return future[0]

    if now.date() in campaign_days:
        return now.date()

    raise SystemExit("No current or future campaign dates remain.")


def load_state(project: Path) -> tuple[Path, dict[str, Any]]:
    path = project / STATE_REL
    state = read_json(path) if path.exists() else {"version": 1, "posts": {}}
    state.setdefault("posts", {})
    return path, state


def historical_sent_days(project: Path) -> set[int]:
    rows: list[dict[str, Any]] = []
    for path in (
        project / "out" / "manifest.jsonl",
        project / "out" / "publish-ledger.jsonl",
        project / ".private" / "publish-ledger.jsonl",
    ):
        rows.extend(read_jsonl(path))

    result: set[int] = set()
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


def buffer_graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    request = urllib.request.Request(
        BUFFER_API,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {required_env('BUFFER_API_KEY')}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Buffer API failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Buffer API connection failed: {exc.reason}") from exc

    parsed = json.loads(text)
    errors = parsed.get("errors") or []
    if errors:
        message = "; ".join(str(error.get("message", error)) for error in errors)
        raise RuntimeError(f"Buffer GraphQL error: {message}")
    data = parsed.get("data")
    if not isinstance(data, dict):
        raise RuntimeError("Buffer returned no data.")
    return data


def buffer_fetch_post(post_id: str) -> dict[str, Any]:
    query = """
      query CandyDuplicatePost($id: PostId!) {
        post(input: {id: $id}) {
          id status dueAt sentAt createdAt allowedActions text
        }
      }
    """
    try:
        data = buffer_graphql(query, {"id": post_id})
        post = data.get("post")
        return post if isinstance(post, dict) else {"id": post_id, "lookupError": "No post returned"}
    except Exception as exc:
        return {"id": post_id, "lookupError": str(exc)}


def buffer_delete_post(post_id: str) -> str:
    mutation = """
      mutation DeleteCandyDuplicate($id: PostId!) {
        deletePost(input: {id: $id}) {
          __typename
          ... on DeletePostSuccess { id }
          ... on VoidMutationError { message }
        }
      }
    """
    data = buffer_graphql(mutation, {"id": post_id})
    result = data.get("deletePost")
    if not isinstance(result, dict):
        raise RuntimeError(f"Buffer returned no deletePost result for {post_id}")
    if result.get("__typename") != "DeletePostSuccess":
        raise RuntimeError(str(result.get("message") or f"Buffer refused to delete {post_id}"))
    return str(result.get("id") or post_id)


def live_status(post: dict[str, Any]) -> str:
    return str(post.get("status") or "").lower()


def can_delete(post: dict[str, Any]) -> bool:
    actions = post.get("allowedActions")
    return isinstance(actions, list) and "deletePost" in actions


def cleanup_buffer_duplicates(project: Path, *, apply: bool) -> dict[str, int]:
    banner("4. BUFFER DUPLICATE GUARD")
    print("Mode:", "APPLY — safe scheduled duplicates may be deleted" if apply else "DRY RUN — nothing will be deleted")

    manifest = read_jsonl(project / "out" / "manifest.jsonl")
    if not manifest:
        print("No local manifest yet. Nothing to clean.")
        return {"groups": 0, "deleted": 0, "blocked": 0, "stale": 0}

    by_day: dict[int, list[dict[str, Any]]] = {}
    for index, row in enumerate(manifest):
        post_id = row.get("bufferPostId")
        if not post_id:
            continue
        try:
            day_num = int(row.get("day"))
        except (TypeError, ValueError):
            continue
        group = by_day.setdefault(day_num, [])
        if not any(item.get("bufferPostId") == post_id for item in group):
            group.append({**row, "_manifestIndex": index})

    duplicate_groups = [(day_num, rows) for day_num, rows in sorted(by_day.items()) if len(rows) > 1]
    if not duplicate_groups:
        print("No duplicate Buffer post IDs found in out/manifest.jsonl.")
        return {"groups": 0, "deleted": 0, "blocked": 0, "stale": 0}

    deleted = 0
    blocked = 0
    stale = 0

    for day_num, rows in duplicate_groups:
        print(f"\nDay/Post {day_num:03d} has {len(rows)} Buffer IDs:")
        live: list[dict[str, Any]] = []
        for row in rows:
            post_id = str(row["bufferPostId"])
            post = buffer_fetch_post(post_id)
            live.append({**row, "_live": post})
            status = post.get("status") or "UNKNOWN"
            due = post.get("dueAt") or row.get("scheduledAt") or "-"
            created = post.get("createdAt") or "-"
            print(f"  {post_id}  status={status}  due={due}  created={created}")
            lookup_error = post.get("lookupError")
            if lookup_error:
                print(f"    LOOKUP ERROR: {lookup_error}")
                if "post not found" in str(lookup_error).lower():
                    stale += 1

        sent = [item for item in live if live_status(item["_live"]) == "sent"]
        scheduled_items = [item for item in live if live_status(item["_live"]) == "scheduled"]
        delete_candidates: list[dict[str, Any]] = []

        if sent:
            delete_candidates = scheduled_items
            print(f"  Decision: {len(sent)} copy/copies already SENT; remove every remaining scheduled duplicate.")
        elif len(scheduled_items) > 1:
            def sort_key(item: dict[str, Any]) -> tuple[float, int]:
                created_raw = item["_live"].get("createdAt")
                created_ts = float("inf")
                if isinstance(created_raw, str):
                    try:
                        created_ts = datetime.fromisoformat(created_raw.replace("Z", "+00:00")).timestamp()
                    except ValueError:
                        pass
                return created_ts, int(item["_manifestIndex"])

            scheduled_items.sort(key=sort_key)
            keeper = scheduled_items[0]
            delete_candidates = scheduled_items[1:]
            print(f"  KEEP: {keeper['bufferPostId']} (oldest scheduled copy)")
        else:
            print("  Decision: no removable scheduled duplicate exists right now.")

        for candidate in delete_candidates:
            post_id = str(candidate["bufferPostId"])
            live_post = candidate["_live"]
            if not can_delete(live_post):
                print(f"  BLOCKED: {post_id} is not currently deletable according to Buffer allowedActions.")
                blocked += 1
                continue
            if not apply:
                print(f"  WOULD DELETE: {post_id}")
                continue
            try:
                deleted_id = buffer_delete_post(post_id)
                print(f"  DELETED: {deleted_id}")
                deleted += 1
            except Exception as exc:
                print(f"  DELETE FAILED: {post_id}: {exc}")
                blocked += 1

    print("\nDuplicate guard summary:")
    print(f"  Groups checked: {len(duplicate_groups)}")
    print(f"  Scheduled duplicates deleted: {deleted}")
    print(f"  Blocked/not deletable: {blocked}")
    print(f"  Stale local Buffer IDs: {stale}")
    print("  Sent TikTok posts are NEVER deleted.")

    return {"groups": len(duplicate_groups), "deleted": deleted, "blocked": blocked, "stale": stale}


def main() -> None:
    parser = argparse.ArgumentParser(description="Candy Trivia all-in-one safe TikTok/Buffer autopilot")
    parser.add_argument("--date", help="Use a specific campaign date YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without rendering, publishing, or deleting")
    parser.add_argument("--skip-pull", action="store_true", help="Skip git checkout/pull (troubleshooting only)")
    args = parser.parse_args()

    project = project_dir()
    if not args.dry_run and (project / '.private' / 'cloud-publisher-cutover.json').exists():
        raise SystemExit('Local publishing retired: use the Candy Python Cloud Autopilot GitHub workflow.')
    load_env_file(project)
    now = datetime.now(TZ)

    if not shutil.which("git"):
        raise SystemExit("git not found in PATH.")
    if not (shutil.which("npm") or shutil.which("npm.cmd")):
        raise SystemExit("npm not found in PATH.")

    banner("CANDY TRIVIA — ALL-IN-ONE SAFE AUTOPILOT")
    print(f"Project: {project}")
    print(f"Branch:  {BRANCH}")
    print(f"Now:     {now.strftime('%Y-%m-%d %I:%M:%S %p %Z')}")
    print("Mode:    " + ("DRY RUN" if args.dry_run else "LIVE"))

    if not args.dry_run:
        banner("1. UPDATE PROJECT")
        if not args.skip_pull:
            run(["git", "checkout", BRANCH], project, "Checkout branch")
            run(["git", "pull", "--ff-only", "origin", BRANCH], project, "Pull latest GitHub changes")
        else:
            print("Skipping git pull by request.")

        banner("2. VALIDATE CODE")
        run([npm(), "run", "typecheck"], project, "TypeScript typecheck")

        banner("3. AUDIT CAMPAIGN CONTENT")
        run([npm(), "run", "audit-content"], project, "Trivia duplicate audit")
    else:
        banner("1-3. DRY RUN — UPDATE / TYPECHECK / CONTENT AUDIT SKIPPED")

    cleanup = cleanup_buffer_duplicates(project, apply=not args.dry_run)

    posts = load_posts(project)
    chosen = choose_target_date(posts, args.date, now)
    selected = sorted([post for post in posts if post["when"].date() == chosen], key=lambda post: post["when"])
    if len(selected) > 3:
        raise SystemExit(f"Safety stop: {len(selected)} posts found for {chosen}; expected <= 3.")

    state_path, state = load_state(project)
    sent_days = historical_sent_days(project)
    sent_fingerprints = {
        item.get("contentFingerprint")
        for item in state["posts"].values()
        if isinstance(item, dict) and item.get("status") == "SENT"
    }

    banner(f"5. SAFETY CHECK — {chosen}")
    ready: list[dict[str, Any]] = []
    skipped: list[int] = []
    blocked_posts: list[int] = []

    for post in selected:
        num = post["num"]
        item = state["posts"].get(f"{num:03d}", {})
        status = item.get("status") if isinstance(item, dict) else None
        print(f"Post {num:03d}: {post['when'].strftime('%I:%M %p %Z')}", end=" — ")

        if num in sent_days or status == "SENT":
            print("SKIP, already sent")
            skipped.append(num)
        elif status == "PUBLISHING":
            print("BLOCKED, prior result uncertain")
            blocked_posts.append(num)
        elif post["fp"] in sent_fingerprints:
            print("BLOCKED, same content already sent")
            blocked_posts.append(num)
        elif post["when"] <= now:
            print("SKIP, scheduled time already passed")
            skipped.append(num)
        else:
            print("READY")
            ready.append(post)

    if args.dry_run:
        banner("DRY RUN COMPLETE — NOTHING CHANGED")
        print("Ready:", [f"{post['num']:03d}" for post in ready])
        print("Skipped:", [f"{num:03d}" for num in skipped])
        print("Blocked/uncertain:", [f"{num:03d}" for num in blocked_posts])
        print("Duplicate groups found:", cleanup["groups"])
        return

    published: list[int] = []

    if ready:
        banner("6. RENDER ONLY NEW POSTS")
        videos: dict[int, Path] = {}
        for post in ready:
            num = post["num"]
            rel = post["path"].relative_to(project)
            run([npm(), "run", "render-local", "--", str(rel)], project, f"Render {num:03d}")
            videos[num] = verify_video(project, num)

        banner("7. PUBLISH EXACTLY ONCE")
        for post in ready:
            num = post["num"]
            sha = video_sha(videos[num])

            # Two-phase safety: persist PUBLISHING before Buffer is called.
            set_state(state_path, state, post, "PUBLISHING", sha=sha)

            rel = post["path"].relative_to(project)
            try:
                run([npm(), "run", "publish", "--", str(rel)], project, f"Publish {num:03d}")
            except SystemExit:
                print(
                    f"\nSAFETY HOLD: Post {num:03d} remains PUBLISHING/UNCERTAIN.\n"
                    "Do NOT rerun that post automatically. Check Buffer/TikTok first."
                )
                raise

            buffer_id = manifest_buffer_id(project, num)
            set_state(state_path, state, post, "SENT", sha=sha, buffer_id=buffer_id)
            published.append(num)
            print(f"Post {num:03d}: SENT" + (f" | Buffer {buffer_id}" if buffer_id else ""))
    else:
        banner("6-7. NO NEW POSTS TO RENDER OR PUBLISH")
        print("Nothing was submitted to Buffer.")

    banner("8. ANALYTICS")
    analytics_ok = run([npm(), "run", "analytics"], project, "Analytics", fatal=False)

    banner("SUCCESS")
    print("Published/scheduled:", [f"{num:03d}" for num in published] if published else "none")
    print("Already-sent/past skipped:", [f"{num:03d}" for num in skipped])
    print("Blocked/uncertain:", [f"{num:03d}" for num in blocked_posts])
    print(f"Safe scheduled duplicates removed: {cleanup['deleted']}")
    print(f"Stale Buffer IDs ignored: {cleanup['stale']}")
    print("Analytics:", "OK" if analytics_ok else "WARNING — see output above")
    print("\nSAFE TO RERUN: SENT and UNCERTAIN posts will not be resubmitted.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(130)
