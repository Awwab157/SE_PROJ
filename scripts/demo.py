"""See the server work, offline, without an LLM or a Google account.

Connects a real MCP client to the server (in-process), using the synthetic sample data in tests/fixtures, and
calls every feature, printing readable results.

Usage: ``python scripts/demo.py``
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import anyio  # noqa: E402
from mcp import Client  # noqa: E402

from yt_intel_mcp.approval import RecordingApprovalPrompt  # noqa: E402
from yt_intel_mcp.duration import format_duration  # noqa: E402
from yt_intel_mcp.server import build_app, create_server  # noqa: E402


def header(title: str) -> None:
    print("\n" + "=" * 78 + f"\n  {title}\n" + "=" * 78)


async def call(client: Client, tool: str, args: dict) -> dict:
    print(f"\n> {tool}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
    result = await client.call_tool(tool, args)
    data = result.structured_content or {}
    if result.is_error:
        err = data["error"]
        print(f"  ERROR [{err['code']}] {err['cause']}\n  Next step: {err['next_step']}")
    else:
        print(f"  {data.get('summary', '')}")
    return data


async def main() -> None:
    prompt = RecordingApprovalPrompt()  # stands in for the local approval page in this demo
    with tempfile.TemporaryDirectory() as state:
        app = build_app(state_dir=Path(state), provider_mode="fixture", approval_prompt=prompt)
        async with Client(create_server(app), mode="legacy") as client:
            tools = (await client.list_tools()).tools
            header(f"Server is running with {len(tools)} tools (sample data, no network)")
            for t in tools:
                writes = "WRITES" if "Writes to YouTube: YES" in t.description else "read-only"
                print(f"  - {t.name:<22} [{writes}]")

            header("1. Similar videos (FR-1)")
            data = await call(client, "find_similar_videos", {"video": "https://youtu.be/pdIntro0001", "limit": 5})
            print(f"  Seed: {data['seed']['title']}")
            for r in data["results"]:
                print(f"   {r['score']:.2f}  {r['title']}  ({r['channel_title']})")
                print(f"         why: {r['explanation']}")

            header("2. Similar channels (FR-2)")
            data = await call(client, "find_similar_channels", {"channel": "@datadojo", "limit": 3})
            for r in data["results"]:
                subs = r["subscriber_count"] if r["subscriber_count"] is not None else "hidden"
                print(f"   {r['score']:.3f}  {r['title']}  (subscribers: {subs})  - {r['explanation']}")
            await call(client, "find_similar_channels", {"channel": "https://www.youtube.com/c/breadlab"})
            print("   (ambiguous /c/ URL: the server lists candidates instead of guessing)")

            header("3. Recommendations from likes, subscriptions and playlists (FR-3)")
            data = await call(client, "recommend_videos", {"limit": 5, "filters": {"max_duration_min": 20}})
            for r in data["results"]:
                print(f"   {r['score']:.2f}  {r['title']}  [{format_duration(r['duration_seconds'])}]")
                print(f"         signals: {'; '.join(r['signals'])}")

            header("4. Engagement analysis (FR-4)")
            data = await call(client, "analyze_engagement", {"period": "2025", "compare_to": "2026"})
            for c in data["top_channels"]["likes"]:
                print(f"   likes by channel: {c['label']:<18} {c['count']}  ({c['share']:.0%})")
            for d in data["durations"]:
                print(f"   {d['source']:<15} durations: {d['buckets']}  median {d['median_minutes']} min")
            for c in data["comparison"]:
                print(f"   {c['source']:<15} 2025 vs 2026: {c['label']}")

            header("5. Playlist: propose, approve, create (FR-5)")
            data = await call(client, "propose_playlist", {
                "topic": "pandas python", "total_duration_min": 60, "max_video_duration_min": 20, "language": "en"})
            for item in data["items"]:
                print(f"   {item['position']}. [{item['level']:<12}] {item['title']}  ({item['duration_text']})")
            print(f"   Total {format_duration(data['total_duration_seconds'])}, excluded: {data['excluded']}")
            print(f"   Estimated write quota: {data['estimated_write_quota']}  - nothing written yet")
            pid = data["proposal_id"]

            await call(client, "create_playlist", {"proposal_id": pid, "confirmation_code": "GUESS123"})
            print("   (a guessed code is rejected - nothing is created)")
            pending = await call(client, "create_playlist", {"proposal_id": pid})
            print(f"   status: {pending['status']}  (in real use a page opens in your browser with the code)")
            code = prompt.last_code
            print(f"   [demo] the user reads the code on that page: {code}")
            done = await call(client, "create_playlist", {"proposal_id": pid, "confirmation_code": code})
            print(f"   URL: {done['playlist_url']}  privacy: {done['privacy']}  quota used: {done['quota_used']}")
            await call(client, "create_playlist", {"proposal_id": pid})
            print("   (repeating returns the existing playlist - no duplicate)")

            header("6. Error handling")
            await call(client, "find_similar_videos", {"video": "not a youtube link"})

            header("Quota used in this demo")
            status = (await client.read_resource("quota://status")).contents[0].text
            print(f"  {status}")


if __name__ == "__main__":
    anyio.run(main)
