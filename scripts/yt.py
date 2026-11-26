"""Use the YouTube Video Intelligence server from the command line (no AI app needed).

Examples (run from the project folder):
    python scripts/yt.py login
    python scripts/yt.py similar https://www.youtube.com/watch?v=VIDEO_ID
    python scripts/yt.py channels @somehandle
    python scripts/yt.py recommend --max-min 20 --lang en
    python scripts/yt.py analyze --period 2025 --compare 2024
    python scripts/yt.py playlist "sourdough baking" --total 60 --max 20 --lang en
    python scripts/yt.py quota
    python scripts/yt.py logout
Add --sample before the command to use the offline sample data instead of your YouTube account.

The CLI talks to the same MCP tools an AI client would use. Playlist creation still needs your approval: a page opens
in your browser with a one-time code, and you type that code here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import anyio  # noqa: E402
from mcp import Client  # noqa: E402

from yt_intel_mcp.duration import format_duration  # noqa: E402
from yt_intel_mcp.server import CLIENT_SECRETS_ENV, build_app, create_server  # noqa: E402

DEFAULT_SECRETS = Path.home() / ".yt-intel-mcp" / "client_secret.json"
SETUP_HINT = f"""No OAuth client file found.
Do the one-time Google Cloud setup in docs/user-guide.md ("Use it from the command line", step 1) and save the
downloaded JSON as:
    {DEFAULT_SECRETS}
(or set {CLIENT_SECRETS_ENV} to its path). Try the offline sample data meanwhile with --sample."""


class ToolFailed(Exception):
    pass


async def call(client: Client, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    result = await client.call_tool(tool, args)
    data = result.structured_content or {}
    if result.is_error:
        err = data.get("error", {})
        raise ToolFailed(f"Error ({err.get('code')}): {err.get('cause')}\nNext step: {err.get('next_step')}")
    return data


def dur(seconds: int | None) -> str:
    return format_duration(seconds)


def show_notes(data: dict[str, Any]) -> None:
    for note in data.get("notes", []) + data.get("data_limits", []):
        print(f"  note: {note}")
    if data.get("quota_used"):
        print(f"  quota used: {data['quota_used']}")


# --- commands -----------------------------------------------------------------------------------------------


async def cmd_login(client: Client, args) -> None:
    print("Opening your browser for Google sign-in (read-only access)...")
    data = await call(client, "start_authorization", {})
    print(data["summary"])


async def cmd_logout(client: Client, args) -> None:
    print((await call(client, "revoke_authorization", {}))["summary"])


async def cmd_similar(client: Client, args) -> None:
    data = await call(client, "find_similar_videos", {"video": args.video, "limit": args.limit})
    seed = data["seed"]
    print(f"Seed video: {seed['title']} - {seed['channel_title']}\n  {seed['url']}")
    print(data["summary"] + "\n")
    for i, r in enumerate(data["results"], 1):
        print(f"{i:>2}. {r['title']}")
        print(f"    {r['channel_title']} | {dur(r['duration_seconds'])} | score {r['score']:.2f}")
        print(f"    {r['url']}")
        print(f"    why: {r['explanation']}")
    show_notes(data)


async def cmd_channels(client: Client, args) -> None:
    data = await call(client, "find_similar_channels", {"channel": args.channel, "limit": args.limit})
    print(data["summary"] + "\n")
    for c in data.get("candidates", []):
        print(f"  candidate: {c['title']}  {c['url']}")
    for i, r in enumerate(data["results"], 1):
        subs = f"{r['subscriber_count']:,}" if r["subscriber_count"] is not None else "hidden"
        print(f"{i:>2}. {r['title']}  (subscribers: {subs})")
        print(f"    {r['url']}")
        print(f"    why: {r['explanation']}")
    show_notes(data)


async def cmd_recommend(client: Client, args) -> None:
    filters = {
        k: v
        for k, v in {"max_duration_min": args.max_min, "language": args.lang, "category": args.category}.items()
        if v is not None
    }
    data = await call(client, "recommend_videos", {"limit": args.limit, "filters": filters})
    print(data["summary"] + "\n")
    for i, r in enumerate(data["results"], 1):
        print(f"{i:>2}. {r['title']}")
        print(f"    {r['channel_title']} | {dur(r['duration_seconds'])} | {r['url']}")
        print(f"    because: {'; '.join(r['signals'])}")
    show_notes(data)


async def cmd_analyze(client: Client, args) -> None:
    payload = {"period": args.period}
    if args.compare:
        payload["compare_to"] = args.compare
    data = await call(client, "analyze_engagement", payload)
    print(data["summary"] + "\n")
    for source, rows in data["top_channels"].items():
        if rows:
            print(f"Top channels ({source}):")
            for c in rows[:5]:
                print(f"  {c['label'] or c['key']:<30} {c['count']:>4}  ({c['share']:.0%})")
    for source, rows in data["top_categories"].items():
        if rows:
            print(f"Top categories ({source}):")
            for c in rows[:5]:
                print(f"  {c['label'] or c['key']:<30} {c['count']:>4}  ({c['share']:.0%})")
    for d in data["durations"]:
        print(f"Video lengths ({d['source']}): {d['buckets']}  median {d['median_minutes']} min")
    for t in data["trends"]:
        if t["granularity"] == "quarter" and t["points"]:
            points = ", ".join(f"{p['period']}: {p['count']}" for p in t["points"])
            print(f"Trend {t['source']} by {t['timestamp_source']}: {points}")
    for c in data["comparison"]:
        print(f"Compare {c['source']}: {c['label']}")
    show_notes(data)


async def cmd_playlist(client: Client, args) -> None:
    payload: dict[str, Any] = {
        "topic": args.topic,
        "total_duration_min": args.total,
        "max_video_duration_min": args.max,
        "language": args.lang,
        "privacy": args.privacy,
    }
    if args.min is not None:
        payload["min_video_duration_min"] = args.min
    data = await call(client, "propose_playlist", payload)
    print(data["summary"] + "\n")
    if data["status"] != "proposed":
        print(data["next_step"])
        return
    print(f"Title: {data['title']}  ({data['privacy']})")
    for item in data["items"]:
        print(
            f"{item['position']:>2}. [{item['level']}] {item['title']} - {item['channel_title']} "
            f"({item['duration_text']})\n    {item['url']}"
        )
    print(f"\nTotal {dur(data['total_duration_seconds'])} of {dur(data['target_duration_seconds'])}")
    for problem in data["unmet_constraints"]:
        print(f"  unmet: {problem}")
    print(f"  excluded: {data['excluded']}")
    print(f"  estimated quota to create it: {data['estimated_write_quota']}")
    if input("\nCreate this playlist on YouTube? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Not created. Nothing was written to YouTube.")
        return
    result = await call(client, "create_playlist", {"proposal_id": data["proposal_id"]})
    if result["status"] == "approval_pending":
        print("A page opened in your browser showing this playlist and a one-time code.")
        code = input("Type the code from that page (or press Enter to cancel): ").strip()
        if not code:
            print("Cancelled. Nothing was written to YouTube.")
            return
        result = await call(client, "create_playlist", {"proposal_id": data["proposal_id"], "confirmation_code": code})
    print(result["summary"])
    if result.get("playlist_url"):
        print(f"Open it: {result['playlist_url']}")
    if result.get("quota_used"):
        print(f"  quota used: {result['quota_used']}")


async def cmd_quota(client: Client, args) -> None:
    status = json.loads((await client.read_resource("quota://status")).contents[0].text)
    print(f"Quota for {status['day']} (resets {status['resets_at']}):")
    for bucket, b in status["buckets"].items():
        print(f"  {bucket:<13} used {b['consumed']:>6} of {b['limit']:>6}  -> {b['remaining']} left")


COMMANDS = {
    "login": cmd_login,
    "logout": cmd_logout,
    "similar": cmd_similar,
    "channels": cmd_channels,
    "recommend": cmd_recommend,
    "analyze": cmd_analyze,
    "playlist": cmd_playlist,
    "quota": cmd_quota,
}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="yt.py", description="YouTube Video Intelligence from the command line.")
    p.add_argument("--sample", action="store_true", help="use the offline sample data (no Google account)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="connect your YouTube account (read-only)")
    sub.add_parser("logout", help="revoke access and delete the stored token and cache")
    s = sub.add_parser("similar", help="videos similar to a video")
    s.add_argument("video", help="YouTube video URL or 11-character ID")
    s.add_argument("--limit", type=int, default=10)
    c = sub.add_parser("channels", help="channels similar to a channel")
    c.add_argument("channel", help="@handle, channel ID or channel URL")
    c.add_argument("--limit", type=int, default=10)
    r = sub.add_parser("recommend", help="recommendations from your likes, subscriptions and playlists")
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--max-min", type=float, help="maximum video length in minutes")
    r.add_argument("--lang", help="ISO 639-1 language code, e.g. en")
    r.add_argument("--category", help="numeric YouTube category ID, e.g. 27 (Education)")
    a = sub.add_parser("analyze", help="analyse your likes, subscriptions and playlists")
    a.add_argument("--period", default="all", help="all | last_N_days | YYYY | YYYY-Qn | YYYY-MM | A..B")
    a.add_argument("--compare", help="period to compare with, same formats")
    pl = sub.add_parser("playlist", help="propose (and, after your approval, create) a playlist")
    pl.add_argument("topic")
    pl.add_argument("--total", type=float, required=True, help="total playlist length in minutes")
    pl.add_argument("--max", type=float, required=True, help="maximum length of one video in minutes")
    pl.add_argument("--min", type=float, help="minimum length of one video in minutes")
    pl.add_argument("--lang", required=True, help="ISO 639-1 language code, e.g. en")
    pl.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    sub.add_parser("quota", help="today's remaining YouTube API quota")
    return p


async def run(args, state_dir: Path | None) -> int:
    app = build_app(provider_mode="fixture" if args.sample else "live", state_dir=state_dir)
    async with Client(create_server(app), mode="legacy") as client:
        try:
            await COMMANDS[args.command](client, args)
        except ToolFailed as exc:  # handled here: raising through the client would wrap it in an ExceptionGroup
            print(exc)
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not args.sample and not os.environ.get(CLIENT_SECRETS_ENV):
        if not DEFAULT_SECRETS.exists():
            print(SETUP_HINT)
            return 1
        os.environ[CLIENT_SECRETS_ENV] = str(DEFAULT_SECRETS)
    try:
        if args.sample:
            with tempfile.TemporaryDirectory() as tmp:
                return anyio.run(run, args, Path(tmp))
        return anyio.run(run, args, None)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
