# User guide

## 1. Install
Requirements: Python 3.11 or newer, a desktop with a web browser (for sign-in and the local approval page).

```bash
git clone <repo-url> yt-intel-mcp && cd yt-intel-mcp
python -m venv .venv
. .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e .
python scripts/local_check.py --skip-tests   # offline sanity check, no account needed
```

## 2. Google Cloud project and OAuth consent
Use **one** Google Cloud project for the team (no extra projects).

1. In Google Cloud Console create (or pick) the project and **enable "YouTube Data API v3"**.
2. *OAuth consent screen*: user type **External**, publishing status **Testing**. Add every tester's Google account
   under *Test users*. Add scopes `.../auth/youtube.readonly` and `.../auth/youtube`.
3. *Credentials → Create credentials → OAuth client ID → Desktop app*. Download the JSON.
4. Store the JSON **outside the repository**, e.g. `~/.yt-intel-mcp/client_secret.json`, and never commit it.

> **Testing mode expires sign-ins after 7 days.** When a tool returns `reauthorization_required`, call
> `start_authorization` again.

## Use it from the command line (no AI app needed)
`scripts/yt.py` calls the same tools an AI client would. Run everything from the project folder in PowerShell
(macOS/Linux: use `.venv/bin/python` and forward slashes).

**Step 1 — Google Cloud setup (one time, about 10 minutes)** at https://console.cloud.google.com
1. Top bar → project picker → **New project** → name it `yt-intel` → **Create**, then select it.
2. **APIs & Services → Library** → search "YouTube Data API v3" → **Enable**.
3. **APIs & Services → OAuth consent screen** → **External** → app name `yt-intel`, your email as support and developer
   contact → save. Under **Audience / Test users** add your own Gmail address. Leave the status on *Testing*.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID** → application type **Desktop app** →
   **Create** → **Download JSON**.
5. Create the folder `C:\Users\<you>\.yt-intel-mcp\` and save the file there as `client_secret.json`.
   Keep it outside the project folder and never commit it.

**Step 2 — Log in** (again every 7 days while the app is in Testing mode)
```powershell
.venv\Scripts\python scripts\yt.py login
```
Your browser opens. Choose your account. On "Google hasn't verified this app" click **Continue** (it is your own app),
then allow read-only access.

**Step 3 — Find videos**
```powershell
.venv\Scripts\python scripts\yt.py similar https://www.youtube.com/watch?v=VIDEO_ID   # related videos + reasons
.venv\Scripts\python scripts\yt.py channels @somehandle                                # similar channels
.venv\Scripts\python scripts\yt.py recommend --max-min 20 --lang en                    # from your likes/subs/playlists
.venv\Scripts\python scripts\yt.py analyze --period 2025 --compare 2024                # your engagement analysis
.venv\Scripts\python scripts\yt.py playlist "sourdough baking" --total 60 --max 20 --lang en
.venv\Scripts\python scripts\yt.py quota                                               # quota left today
.venv\Scripts\python scripts\yt.py logout                                              # disconnect
```
`playlist` shows the proposal and asks "Create this playlist on YouTube? [y/N]". On yes, a page opens in your browser
with a one-time code; type it in the terminal and the (private) playlist is created. The first time, Google asks for
the extra "manage your YouTube account" permission. Add `--sample` before the command (e.g.
`yt.py --sample similar pdIntro0001`) to try everything with offline sample data. `yt.py --help` lists all options.

Each `similar` call uses about 3 of the 100 daily search calls; `quota` shows what is left (resets at midnight
Pacific Time).

## 3. Configure your MCP client
Environment variables:

| Variable | Purpose | Default |
|---|---|---|
| `YT_INTEL_CLIENT_SECRETS` | Path to the OAuth Desktop-app JSON | — (required for live use) |
| `YT_INTEL_STATE_DIR` | State directory (SQLite cache, quota ledger, proposals) | `~/.yt-intel-mcp` |
| `YT_INTEL_PROVIDER` | `live` or `fixture` (offline demo data) | `live` |
| `YT_INTEL_LOCAL_APPROVAL` | `auto` or `disabled` (disables the local approval page) | `auto` |
| `YT_INTEL_CONFIG_DIR` | Alternative directory for `quota.yaml` / `similarity.yaml` | `config/` in the repo |

**Claude Desktop** (`claude_desktop_config.json`; on Windows `%APPDATA%\Claude\claude_desktop_config.json`, on macOS
`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "yt-intel": {
      "command": "C:\\path\\to\\yt-intel-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "yt_intel_mcp"],
      "env": {
        "YT_INTEL_CLIENT_SECRETS": "C:\\Users\\<you>\\.yt-intel-mcp\\client_secret.json"
      }
    }
  }
}
```
On macOS/Linux use `/path/to/yt-intel-mcp/.venv/bin/python`. Restart the client after editing. To try the server
without an account, set `"YT_INTEL_PROVIDER": "fixture"`.

## 4. First use
Ask the assistant to *"connect my YouTube account"* → it calls `start_authorization`, your browser opens Google's
consent page (read-only access). Approve it and return to the client.

## 5. Supported prompts (examples)
- "Find videos similar to https://youtu.be/VIDEO_ID" → `find_similar_videos`
- "Which channels are like @somehandle?" → `find_similar_channels`
- "Recommend 10 videos under 15 minutes in English" → `recommend_videos`
- "Analyse my likes, subscriptions and playlists for 2025 compared with 2024" → `analyze_engagement`
- "Make a 60-minute playlist about sourdough baking, videos at most 20 minutes, English" → `propose_playlist`
- "Turn this video into a playlist" → the `video-to-playlist` skill (`skills/video-to-playlist/SKILL.md`): it
  summarises the video from its metadata, finds similar videos and proposes a playlist built from *those* videos
  (`propose_playlist` with `candidate_video_ids`)
- "How much quota is left?" → resource `quota://status`

Playlist requests are written in natural language. The assistant turns them into the structured constraints of
`propose_playlist` (topic, total duration, maximum video length, language), and the proposal lists every constraint
check so you can see how your request was read.

Results only use video metadata and your likes, subscriptions and playlists. Summaries are metadata-based, not
transcripts. Viewing history is not available through the API and is never used.

## 6. Playlist confirmation
1. `propose_playlist` shows the exact videos, total duration, checks, exclusions and estimated quota. Nothing is written.
2. When you ask to create it, `create_playlist` asks **you** directly:
   - If your client supports confirmation dialogs (MCP elicitation), a dialog shows the proposal: accept, decline
     or cancel.
   - Otherwise a **local approval page** opens in your browser with the proposal and a one-time code. If you approve,
     type the code into the chat. The assistant never sees the code unless you type it.
   - If neither is possible, nothing is created.
3. The playlist is created (private unless you chose otherwise); the result shows its URL and the quota used.
Proposals expire after 10 minutes. Repeating a confirmation never creates a second playlist.

To unlock playlist creation the first time, your browser asks for the additional "manage your YouTube account"
permission. Read features never ask for it.

## 7. Common errors
| Code | Meaning | What to do |
|---|---|---|
| `authorization_required` | Not signed in | Ask to connect the account (`start_authorization`) |
| `reauthorization_required` | Sign-in expired or revoked (7-day Testing limit) | `start_authorization` again |
| `quota_budget_exceeded` | Request would exceed today's quota | Lower the limit or wait for midnight Pacific Time |
| `quota_exceeded` | YouTube reports the quota is used up | Wait for the daily reset |
| `rate_limited` / `transient_error` | Temporary YouTube problem | Try again shortly |
| `not_found` | Video/channel private, deleted or mistyped | Check the URL |
| `youtube_signup_required` | Your Google account has no YouTube channel | Create one, then retry |
| `approval_unavailable` | No safe way to ask you for approval | Use a desktop session / a client with confirmation dialogs |
| `proposal_expired` | More than 10 minutes passed | Propose again |

To disconnect: ask to revoke authorisation (`revoke_authorization`): the token is revoked and deleted, cached data
removed. `clear_cache` removes cached data only.

## 8. Tested environments (NFR-17)
| OS | Python | Status |
|---|---|---|
| Windows 11 | 3.13 | Tested locally (offline suite, `local-check`, stdio server) |
| Ubuntu (GitHub Actions) | 3.11, 3.12 | In CI matrix |
| Windows (GitHub Actions) | 3.11, 3.12 | In CI matrix |
| macOS | — | Not yet tested (TBD) |
