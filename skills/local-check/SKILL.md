---
name: local-check
description: Verify a local checkout of yt-intel-mcp works end to end without network access or a YouTube account. Use before opening a pull request, after pulling changes, or when setting up a team machine. Builds the package, runs lint and tests, starts the MCP server with the fixture provider, calls one read-only tool and reports PASS/FAIL for each of the five steps.
---
# local-check (SK-2)

## Steps
Run from the repository root inside the project's virtual environment:

```bash
python scripts/local_check.py          # full check
python scripts/local_check.py --skip-tests   # quick check of build + server
```

The script performs and reports, in order:
1. **build** — `pip install -e . --no-deps`
2. **tests** — `ruff check` and the offline `pytest` suite (fixtures only)
3. **start** — launches `python -m yt_intel_mcp` over stdio with `YT_INTEL_PROVIDER=fixture`, a temporary state directory and local approval disabled; expects 9 tools
4. **call** — calls the read-only tool `find_similar_videos` (`pdIntro0001`) through a real MCP client session; expects `status: ok`
5. **stop** — the server shuts down cleanly

## Reporting
- Print the five `[PASS]`/`[FAIL]` lines exactly as the script prints them, then the final line.
- On a failure, show the failing step's detail and suggest the next action (for example `pip install -e ".[dev]"` for a build failure, or the failing test name).
- Never run the live provider or ask for credentials in this skill.

## Related notes
- [[mcp]] — stdio transport and in-process testing
- [[mcp-servers-tools-and-resources]]
