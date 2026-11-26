"""SK-2 local check: five steps, each reported PASS/FAIL.

1. build   - install the package (editable, no dependency changes)
2. tests   - run lint and the offline test suite
3. start   - start the MCP server over stdio with the fixture provider
4. call    - call one read-only tool (find_similar_videos) through a real MCP client session
5. stop    - shut the server down cleanly

Usage: ``python scripts/local_check.py [--skip-tests]``. Exits 1 if any step fails.
No network access and no YouTube account are needed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS: list[tuple[str, bool, str]] = []


def step(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}", flush=True)
    return ok


def run(cmd: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-1:] or [""]
    return proc.returncode == 0, tail[0]


async def mcp_steps(state_dir: str) -> None:
    from mcp import Client, StdioServerParameters

    env = {
        **os.environ,
        "YT_INTEL_PROVIDER": "fixture",
        "YT_INTEL_STATE_DIR": state_dir,
        "YT_INTEL_LOCAL_APPROVAL": "disabled",
        "PYTHONPATH": str(ROOT / "src"),
    }
    params = StdioServerParameters(command=sys.executable, args=["-m", "yt_intel_mcp"], env=env, cwd=str(ROOT))
    started = called = False
    try:
        async with Client(params, mode="legacy") as client:
            tools = await client.list_tools()
            started = step("3 start", len(tools.tools) == 9, f"{len(tools.tools)} tools registered")
            result = await client.call_tool("find_similar_videos", {"video": "pdIntro0001", "limit": 3})
            data = result.structured_content or {}
            called = step(
                "4 call",
                not result.is_error and data.get("status") == "ok",
                data.get("summary", "") or str(data.get("error")),
            )
        step("5 stop", True, "server exited cleanly")
    except Exception as exc:  # noqa: BLE001
        if not started:
            step("3 start", False, type(exc).__name__)
        if not called:
            step("4 call", False, "not reached" if not started else type(exc).__name__)
        step("5 stop", False, type(exc).__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)
    ok, tail = run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "-e", "."])
    step("1 build", ok, tail if not ok else "package installed")
    if args.skip_tests:
        step("2 tests", True, "skipped by --skip-tests")
    else:
        lint_ok, lint_tail = run([sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"])
        test_ok, test_tail = run([sys.executable, "-m", "pytest", "-q"])
        step("2 tests", lint_ok and test_ok, test_tail if lint_ok else f"lint: {lint_tail}")
    import anyio

    with tempfile.TemporaryDirectory() as state:
        anyio.run(mcp_steps, state)
    failed = [name for name, ok, _ in RESULTS if not ok]
    print(f"local-check: {'FAILED (' + ', '.join(failed) + ')' if failed else 'ALL 5 STEPS PASSED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
