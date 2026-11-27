# Setting up yt-intel-mcp on a new computer

This guide takes you from a computer with nothing installed to asking Claude Desktop for YouTube results. It takes about
20 minutes, or 30 if you also have to create the Google Cloud project.

Commands are for **Windows PowerShell**. For macOS or Linux, see [section 11](#11-macos-and-linux).

**Contents**
1. [What you need](#1-what-you-need)
2. [Install Python](#2-install-python)
3. [Get the project](#3-get-the-project)
4. [Create the virtual environment](#4-create-the-virtual-environment)
5. [Offline check](#5-offline-check-no-google-account-needed)
6. [Google Cloud: client file and test user](#6-google-cloud-client-file-and-test-user)
7. [Sign in](#7-sign-in)
8. [Try it from the terminal](#8-try-it-from-the-terminal)
9. [Connect Claude Desktop](#9-connect-claude-desktop)
10. [Connect Claude Code (optional)](#10-connect-claude-code-optional)
11. [macOS and Linux](#11-macos-and-linux)
12. [Demo mode without a Google account](#12-demo-mode-without-a-google-account)
13. [Day-to-day notes](#13-day-to-day-notes)
14. [Troubleshooting](#14-troubleshooting)
15. [Removing it from a computer](#15-removing-it-from-a-computer)

---

## 1. What you need

| Item | Notes |
|---|---|
| Python **3.11 or newer** | Check with `python --version` |
| Git | Only if you clone the repository. You can copy the folder instead |
| A web browser on the same computer | Google sign-in and the playlist approval page open in it |
| The OAuth client file `client_secret.json` | From the team's Google Cloud project ([section 6](#6-google-cloud-client-file-and-test-user)) |
| A Google account listed as a **test user** | Added by the person who owns the Google Cloud project |
| Claude Desktop | Only for using it through Claude. The terminal works without it |

> **Never** put `client_secret.json`, tokens or real account data in the repository, a chat with an AI, an email or a
> screenshot.

---

## 2. Install Python

1. Download Python 3.11 or newer from <https://www.python.org/downloads/>.
2. In the installer, tick **"Add python.exe to PATH"**, then click **Install Now**.
3. Open a **new** PowerShell window and check:
   ```powershell
   python --version      # must print 3.11 or newer
   ```

---

## 3. Get the project

Clone the repository:
```powershell
cd $HOME\Desktop
git clone <repo-url> yt-intel-mcp
cd yt-intel-mcp
```
Or copy the project folder from another computer, **without** its `.venv` folder. A virtual environment contains paths
specific to the computer it was made on and doesn't work after copying.

Pick a permanent place for the folder. Claude Desktop starts the server from this path, so moving or renaming the
folder later breaks the connection ([section 13](#13-day-to-day-notes)).

---

## 4. Create the virtual environment

Run this from the project folder:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```
When the environment is active, your prompt starts with `(.venv)`. Activate it again in every new terminal window
before running project commands.

If PowerShell says *"running scripts is disabled on this system"*, run this once and then activate again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Developers who also want to run the tests and linter should install with `pip install -e ".[dev]"`.

---

## 5. Offline check (no Google account needed)

```powershell
python scripts\local_check.py --skip-tests
```
The last line must be **`local-check: ALL 5 STEPS PASSED`**. This builds the package, starts the MCP server, calls a
tool with the offline sample data and stops the server again.

To see every feature work on the sample data:
```powershell
python scripts\demo.py
```

If this step fails, don't continue: fix the installation first ([section 14](#14-troubleshooting)).

---

## 6. Google Cloud: client file and test user

The team uses **one** Google Cloud project. Don't create another one if the team already has it.

### 6a. If the team project already exists (most people)

Ask the project owner for two things:
1. **Add your Google account as a test user.** Owner: Cloud Console → *APIs & Services → OAuth consent screen* →
   *Audience / Test users* → **Add users**.
2. **Give you `client_secret.json`** privately, e.g. on a USB stick or through a password manager. Don't send it
   through git, email or chat.

### 6b. If you are the owner and the project doesn't exist yet

At <https://console.cloud.google.com>:
1. Use the project picker → **New project** → name it (e.g. `yt-intel`) → **Create**, then select it.
2. *APIs & Services → Library* → search **YouTube Data API v3** → **Enable**.
3. *APIs & Services → OAuth consent screen*:
   - User type **External**. Enter an app name, your email as support and developer contact, then save.
   - Scopes: add `.../auth/youtube.readonly` and `.../auth/youtube`.
   - *Audience / Test users*: add every Google account that will sign in.
   - Leave the publishing status on **Testing**.
4. *APIs & Services → Credentials → Create credentials → OAuth client ID*:
   - Application type **Desktop app**. Don't choose "Web application": its sign-in fails with
     `redirect_uri_mismatch`.
   - Click **Create**, then **Download JSON**.

### 6c. Put the file in place

Save it **outside the project folder**:
```powershell
New-Item -ItemType Directory -Force "$HOME\.yt-intel-mcp"
Move-Item "$HOME\Downloads\client_secret_*.json" "$HOME\.yt-intel-mcp\client_secret.json"
```
The terminal tool looks for `%USERPROFILE%\.yt-intel-mcp\client_secret.json` automatically.

**If you only have the client ID and secret** (no downloaded file), create
`%USERPROFILE%\.yt-intel-mcp\client_secret.json` with this content and fill in the two values:
```json
{
  "installed": {
    "client_id": "PASTE_CLIENT_ID_HERE.apps.googleusercontent.com",
    "client_secret": "PASTE_CLIENT_SECRET_HERE",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "redirect_uris": ["http://localhost"]
  }
}
```
Replace the whole `client_id` value, which already ends in `.apps.googleusercontent.com`.

---

## 7. Sign in

```powershell
python scripts\yt.py login
```
1. Your browser opens. Choose the Google account that was added as a test user.
2. On *"Google hasn't verified this app"*, click **Continue**. It's your team's own app.
3. Allow **read-only** access to YouTube.
4. The terminal prints **`YouTube account connected with read-only access.`**

The sign-in is stored in **Windows Credential Manager** on this computer only. It isn't in the project folder and isn't
copied with it.

> While the Google app is in *Testing* mode, **Google expires the sign-in after 7 days**. Run `yt.py login` again when a
> tool reports `reauthorization_required`.

---

## 8. Try it from the terminal

```powershell
python scripts\yt.py quota
python scripts\yt.py similar https://www.youtube.com/watch?v=<VIDEO_ID> --limit 5
python scripts\yt.py quota
```
You should see real video titles with a score and a "why:" line for each. The second `quota` should show about
3 search calls and about 300 units used.

All commands:

| Command | What it does |
|---|---|
| `yt.py similar <url or id>` | Videos similar to a video |
| `yt.py channels @handle` | Channels similar to a channel |
| `yt.py recommend --max-min 20 --lang en` | Recommendations from your likes, subscriptions and playlists |
| `yt.py analyze --period 2025 --compare 2024` | Analysis of your likes, subscriptions and playlists |
| `yt.py playlist "<topic>" --total 60 --max 20 --lang en` | Proposes a playlist and creates it only after your approval |
| `yt.py quota` | Quota used and left today |
| `yt.py logout` | Revokes access and deletes the stored sign-in and cache |
| `yt.py --sample <command>` | Runs any command on the offline sample data |

The terminal tool is a real MCP client of the same server that Claude uses, so a result here is what Claude would get.

---

## 9. Connect Claude Desktop

Claude Desktop starts the server by itself whenever the app is open. You never start a server yourself.

### 9a. Find the config file

| Claude Desktop install | Config file |
|---|---|
| Windows, installer from claude.ai | `%APPDATA%\Claude\claude_desktop_config.json` |
| Windows, Microsoft Store | `%LOCALAPPDATA%\Claude-Data\claude_<id>\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

To find out which one you have on Windows:
```powershell
Get-ChildItem "$env:APPDATA\Claude", "$env:LOCALAPPDATA\Claude-Data" -Recurse -Filter claude_desktop_config.json -ErrorAction SilentlyContinue | Select-Object FullName, LastWriteTime
```
Use the file the app has written to most recently. If there's no file at all, open Claude Desktop once, go to
*Settings → Developer → Edit config*, and it creates one.

### 9b. Edit it

1. **Quit Claude Desktop completely**: right-click its icon in the system tray (bottom-right of the taskbar) →
   **Quit**. The app rewrites this file while it runs, so editing it while the app is open can lose your change.
2. Make a backup copy of the file.
3. Add an `"mcpServers"` entry **next to the settings already there**. Don't delete the rest of the file. Replace
   `<PROJECT>` with the full path of the project folder and `<YOU>` with your Windows user name. Write every backslash
   twice:
   ```json
   {
     "mcpServers": {
       "yt-intel": {
         "command": "C:\\<PROJECT>\\.venv\\Scripts\\python.exe",
         "args": ["-m", "yt_intel_mcp"],
         "env": {
           "YT_INTEL_CLIENT_SECRETS": "C:\\Users\\<YOU>\\.yt-intel-mcp\\client_secret.json"
         }
       }
     },
     "...": "the settings that were already in the file stay here"
   }
   ```
4. Check that the file is still valid JSON:
   ```powershell
   Get-Content "<path to claude_desktop_config.json>" -Raw | ConvertFrom-Json | Select-Object -ExpandProperty mcpServers
   ```
   An error here means a missing comma, quote or backslash.

### 9c. Test it

1. Open Claude Desktop and switch to **Chat** mode (the speech-bubble icon at the top-left, not `</>`).
2. Start a new chat and ask:
   > Find videos similar to https://www.youtube.com/watch?v=<VIDEO_ID>
3. You should see a line **"yt-intel: Find similar videos ›"** above the answer. Click `›` to see the exact request
   Claude sent and the JSON your server returned.

Some versions of Claude Desktop don't list local servers in the **+** menu. That's normal: if the tool line appears, it
works. While the app is open, Task Manager shows a few `python.exe` processes. Those are the server.

**Example prompts**
- "Which channels are like @somehandle?"
- "Recommend 10 videos under 15 minutes in English"
- "Analyse my likes, subscriptions and playlists for 2025 compared with 2024"
- "Make a 60-minute playlist about the Quantum Fourier Transform, videos 5 to 20 minutes, English, beginner to
  advanced. Show me the proposal first."

"How much quota is left?" is offered as the MCP **resource** `quota://status`. Claude Desktop chat doesn't read
resources by itself, so use `yt.py quota` in the terminal for this.

---

## 10. Connect Claude Code (optional)

Claude Code (the `</>` mode in Claude Desktop, the VS Code extension and the CLI) reads its own server list, not
`claude_desktop_config.json`. You have two options:

- **Every folder, for this user:**
  ```powershell
  claude mcp add yt-intel --scope user -e YT_INTEL_CLIENT_SECRETS=C:\Users\<YOU>\.yt-intel-mcp\client_secret.json -- C:\<PROJECT>\.venv\Scripts\python.exe -m yt_intel_mcp
  ```
- **This project folder only:** create `.mcp.json` in the project folder with the same `mcpServers` block as in
  section 9b. It contains paths specific to your computer, so don't commit it.

In Claude Code, `/mcp` lists the server and its tools.

---

## 11. macOS and Linux

| Step | Command |
|---|---|
| Create the venv | `python3 -m venv .venv && . .venv/bin/activate && pip install -e .` |
| Offline check | `python scripts/local_check.py --skip-tests` |
| Client file | `mkdir -p ~/.yt-intel-mcp && mv ~/Downloads/client_secret_*.json ~/.yt-intel-mcp/client_secret.json` |
| Sign in | `python scripts/yt.py login` (the sign-in goes into the macOS Keychain or the Linux Secret Service) |
| Claude Desktop `command` | `/path/to/yt-intel-mcp/.venv/bin/python` |
| Claude Desktop `YT_INTEL_CLIENT_SECRETS` | `/Users/<you>/.yt-intel-mcp/client_secret.json` |

If no secure keyring is available (e.g. a Linux server without a desktop), the sign-in is saved in an encrypted file
in `~/.yt-intel-mcp` with permissions `0600`. macOS hasn't been fully tested yet.

---

## 12. Demo mode without a Google account

To show the project on a computer without Google setup, do sections 2–5 only, then set the provider to the offline
sample data:

- **Terminal:** `python scripts\yt.py --sample similar pdIntro0001`
- **Claude Desktop:** add `"YT_INTEL_PROVIDER": "fixture"` to the `env` block of section 9b.

Every tool then works on synthetic data in `tests/fixtures/`. Nothing is sent to YouTube.

---

## 13. Day-to-day notes

- **Nothing runs in the background.** Claude Desktop starts the server when it opens and stops it when you quit it from
  the tray. The terminal tool starts and stops it for each command.
- **Sign-in:** run `yt.py login` again every 7 days while the Google app is in Testing mode.
- **Quota is per Google Cloud project, shared by every computer and person using the same client file:**
  - 10,000 units and 100 search calls a day, reset at midnight Pacific Time.
  - Each computer's quota record (`yt.py quota`) counts only its own calls.
  - The true shared total is in Cloud Console → *APIs & Services → YouTube Data API v3 → Quotas*.
- **Typical costs:** a similar-video search is about 3 search calls and 300 units. A repeated request is served from
  the local cache and costs 0. Creating a playlist costs 50 units plus 50 per video.
- **Don't move or rename the project folder or delete `.venv`.** If you do, update the `command` path in the Claude
  Desktop config.
- **Local data** lives in `%USERPROFILE%\.yt-intel-mcp\`: the cache, the quota record and playlist proposals.
  `YT_INTEL_STATE_DIR` changes this location.

**Environment variables**

| Variable | Purpose | Default |
|---|---|---|
| `YT_INTEL_CLIENT_SECRETS` | Path to the OAuth Desktop-app JSON | `~/.yt-intel-mcp/client_secret.json` (terminal tool only) |
| `YT_INTEL_STATE_DIR` | Folder for the cache, quota record and proposals | `~/.yt-intel-mcp` |
| `YT_INTEL_PROVIDER` | `live` or `fixture` (offline sample data) | `live` |
| `YT_INTEL_LOCAL_APPROVAL` | `auto` or `disabled` (turns off the browser approval page) | `auto` |
| `YT_INTEL_CONFIG_DIR` | Another folder for `quota.yaml` / `similarity.yaml` | `config/` in the project |

---

## 14. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `No OAuth client file found` | `client_secret.json` isn't at the expected path | Section 6c, or set `YT_INTEL_CLIENT_SECRETS` |
| Browser shows **Error 403: access_denied** | Your Google account isn't a test user | Project owner adds it (section 6a) |
| Browser shows **redirect_uri_mismatch** | The client is a "Web application" | Create a **Desktop app** client (section 6b, step 4) |
| `authorization_required` | Not signed in on this computer | `yt.py login` |
| `reauthorization_required` | Sign-in expired (7 days) or was revoked | `yt.py login` |
| `quota_budget_exceeded` | The request would go over today's quota | Lower the limit or wait for midnight Pacific Time |
| `quota_exceeded` | YouTube reports the project's quota is used up, possibly by another computer | Wait for the daily reset |
| `not_found` | Video or channel is private, deleted or mistyped | Check the URL |
| `youtube_signup_required` | The Google account has no YouTube channel | Create one at youtube.com, then retry |
| `approval_unavailable` | No way to ask you to approve a playlist | Use a desktop session with a browser |
| `proposal_expired` | More than 10 minutes since the playlist proposal | Ask for a new proposal |
| yt-intel tools never appear in Claude Desktop | Wrong config file, invalid JSON, or the app wasn't fully quit | Section 9a; validate the JSON (9b step 4); quit from the tray and reopen |
| Tools still missing after that | The server fails to start | Run the `command` from the config by hand: `C:\<PROJECT>\.venv\Scripts\python.exe -m yt_intel_mcp`. It should log `event=server_start` and then wait (Ctrl+C to stop). Check the logs under *Settings → Developer* in Claude Desktop |
| `can't open file ...\demo.py` | Script run from the wrong place | Scripts are in `scripts\`: `python scripts\demo.py` |
| `running scripts is disabled` when activating | PowerShell execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `local_check.py` fails | Incomplete installation | Activate `.venv`, run `pip install -e .` again, check `python --version` ≥ 3.11 |

---

## 15. Removing it from a computer

1. `python scripts\yt.py logout` revokes the Google sign-in and deletes the stored token and cached data.
2. Remove the `yt-intel` entry from the Claude Desktop config (quit the app first). For Claude Code, also run
   `claude mcp remove yt-intel` or delete `.mcp.json`.
3. Delete `%USERPROFILE%\.yt-intel-mcp\`, which contains `client_secret.json`.
4. Delete the project folder.

To stop a Google account's access without the computer, go to <https://myaccount.google.com/permissions>, choose the
app and click **Remove access**.

See also: [User guide](user-guide.md) · [API reference](api.md) · [Architecture](architecture.md)
