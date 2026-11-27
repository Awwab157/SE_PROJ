"""Build docs/design.pdf from docs/architecture.md and docs/adr/*.md (SE-2).

The Markdown and the Mermaid diagrams are rendered by a headless Chromium browser (Microsoft Edge or Google Chrome),
using marked and mermaid from the jsDelivr CDN, so the machine needs one of those browsers and internet access.
No project data is sent anywhere: the page is a local file and only the two libraries are downloaded.

    python scripts/build_design_pdf.py              # writes docs/design.pdf
    python scripts/build_design_pdf.py --html out.html   # also keep the intermediate HTML

Run it after every change to docs/architecture.md or docs/adr/.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUTPUT = DOCS / "design.pdf"
MARKED = "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js"
MERMAID = "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js"

BROWSERS = [
    os.environ.get("YT_INTEL_BROWSER", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "microsoft-edge",
]

CSS = """
@page { size: A4; margin: 16mm 14mm 18mm 14mm; }
body { font-family: "Segoe UI", Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.45; color: #1d2330; }
h1 { font-size: 20pt; color: #17324d; border-bottom: 2px solid #2f6690; padding-bottom: 4px; }
h2 { font-size: 14pt; color: #17324d; margin-top: 18px; border-bottom: 1px solid #d0d7e2; padding-bottom: 2px; }
h3 { font-size: 11.5pt; color: #2f6690; }
h1, h2, h3 { break-after: avoid; page-break-after: avoid; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 8.6pt; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th, td { border: 1px solid #c9d1dc; padding: 3px 6px; vertical-align: top; text-align: left; }
th { background: #eef2f7; }
code { font-family: Consolas, "Courier New", monospace; font-size: 8.6pt; background: #f2f4f7; padding: 0 2px; }
pre:not(.mermaid) { background: #f6f8fa; padding: 6px; font-size: 8.4pt; white-space: pre-wrap; }
.mermaid { text-align: center; margin: 10px 0; page-break-inside: avoid; }
.mermaid svg { max-width: 100% !important; height: auto; }
a { color: #2f6690; text-decoration: none; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center; text-align: center; }
.cover h1 { border: none; font-size: 28pt; }
.cover p { font-size: 12pt; color: #4a5568; }
.section { page-break-before: always; }
.toc li { margin: 2px 0; }
"""

SCRIPT = """
marked.setOptions({ gfm: true });
const renderer = new marked.Renderer();
const baseCode = renderer.code.bind(renderer);
renderer.code = (code, lang) => lang === 'mermaid'
  ? '<pre class="mermaid">' + code.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</pre>'
  : baseCode(code, lang);
const root = document.getElementById('content');
for (const doc of DOCS) {
  const div = document.createElement('div');
  div.className = 'section';
  div.innerHTML = marked.parse(doc.markdown, { renderer });
  root.appendChild(div);
}
mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict',
  flowchart: { useMaxWidth: true }, sequence: { useMaxWidth: true } });
mermaid.run({ querySelector: '.mermaid' })
  .then(() => { document.title = 'READY'; })
  .catch(err => { document.title = 'MERMAID-ERROR'; document.body.insertAdjacentHTML('beforeend',
    '<pre style="color:red">Diagram error: ' + String(err) + '</pre>'); });
"""


def find_browser() -> str:
    for candidate in BROWSERS:
        if not candidate:
            continue
        path = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if path:
            return path
    raise SystemExit("No Edge or Chrome found. Set YT_INTEL_BROWSER to a Chromium-based browser executable.")


def collect_docs() -> list[dict[str, str]]:
    docs = [{"name": "architecture.md", "markdown": (DOCS / "architecture.md").read_text(encoding="utf-8")}]
    for adr in sorted((DOCS / "adr").glob("*.md")):
        docs.append({"name": adr.name, "markdown": adr.read_text(encoding="utf-8")})
    return docs


def build_html(docs: list[dict[str, str]]) -> str:
    adrs = "".join(f"<li>{d['markdown'].splitlines()[0].lstrip('# ').strip()}</li>" for d in docs[1:])
    cover = (
        '<div class="cover"><h1>YouTube Video Intelligence MCP Server</h1>'
        "<p>System architecture and design &middot; release 1.0</p>"
        f"<p>Generated {date.today().isoformat()} from <code>docs/architecture.md</code> and <code>docs/adr/</code></p>"
        '<div class="toc" style="text-align:left;margin:30px auto 0;width:70%"><b>Contents</b><ol>'
        "<li>Architecture and design (goals, context, deployment, components, provider abstraction, MCP surface, "
        "workflows, state machine, data model, similarity, quota, errors, security, tests, knowledge base, "
        "concurrency, decisions)</li>"
        f"<li>Architecture decision records<ol>{adrs}</ol></li></ol></div></div>"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'><title>LOADING</title>"
        f"<style>{CSS}</style></head><body>{cover}<div id='content'></div>"
        f"<script>const DOCS = {json.dumps(docs)};</script>"
        f"<script src='{MARKED}'></script><script src='{MERMAID}'></script>"
        f"<script>{SCRIPT}</script></body></html>"
    )


def render(browser: str, html_path: Path, pdf_path: Path) -> None:
    with tempfile.TemporaryDirectory() as profile:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=30000",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)


def check_diagrams(browser: str, html_path: Path) -> None:
    """Fail if Mermaid reported a syntax error (the title is set by the page script)."""
    with tempfile.TemporaryDirectory() as profile:
        out = subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                f"--user-data-dir={profile}",
                "--virtual-time-budget=30000",
                "--dump-dom",
                html_path.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=180,
            text=True,
            encoding="utf-8",
        ).stdout
    if "<title>READY</title>" not in out:
        detail = "Diagram error" if "Diagram error" in out else "the libraries did not load (no internet?)"
        raise SystemExit(f"Rendering failed: {detail}.")
    count = out.count("<svg")
    print(f"diagrams rendered: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--html", type=Path, help="also write the intermediate HTML here")
    parser.add_argument("--out", type=Path, default=OUTPUT, help="PDF path (default docs/design.pdf)")
    args = parser.parse_args()
    browser = find_browser()
    html = build_html(collect_docs())
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "design.html"
        html_path.write_text(html, encoding="utf-8")
        if args.html:
            args.html.write_text(html, encoding="utf-8")
        check_diagrams(browser, html_path)
        render(browser, html_path, args.out.resolve())
    size = args.out.stat().st_size
    print(f"wrote {args.out} ({size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
