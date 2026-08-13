"""Assemble output/dashboard.html from output/data.json and the inline assets.

Fails loud, like analysis/build_data.py and unlike .claude/hooks/. The gate that
matters here is assert_self_contained: a dashboard that silently reaches for a
CDN is broken the moment it is opened offline or pasted behind a strict CSP, and
the failure is invisible until then. Nothing is written unless it passes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "dashboard_assets"

# Load order matters: boot.js owns the namespace, app.js runs last.
ASSET_ORDER = (
    "css/dashboard.css",
    "js/boot.js",
    "js/core.js",
)

REQUIRED_KEYS = ("meta", "totals", "correlations", "caveats", "cities", "regions", "countries")

# XML namespace identifiers. createElementNS requires these exact strings and
# nothing is ever fetched from them.
ALLOWED_URL_LITERALS = (
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/1999/xlink",
)

_EXTERNAL_PATTERNS = (
    (re.compile(r"<link\b", re.I), "<link> element"),
    (re.compile(r"\bsrc\s*=", re.I), "src attribute"),
    (re.compile(r"\bsrcset\s*=", re.I), "srcset attribute"),
    (re.compile(r"@import\b", re.I), "@import rule"),
    (re.compile(r"<iframe\b", re.I), "<iframe> element"),
    (re.compile(r"\bintegrity\s*=", re.I), "integrity attribute (implies a remote asset)"),
    (re.compile(r"https?://\S+", re.I), "absolute URL"),
    (re.compile(r"""(?:href|src)\s*=\s*["']//""", re.I), "protocol-relative URL"),
    (re.compile(r"""url\(\s*(?!["']?(?:data:|#))""", re.I), "non-data url() reference"),
)


class DashboardBuildError(Exception):
    """Raised when the dashboard cannot be assembled or fails a gate."""


def assert_self_contained(html: str) -> None:
    """Reject any reference that would leave the page needing the network."""
    scanned = html
    for literal in ALLOWED_URL_LITERALS:
        scanned = scanned.replace(literal, "")

    for pattern, description in _EXTERNAL_PATTERNS:
        match = pattern.search(scanned)
        if match:
            raise DashboardBuildError(
                f"external reference ({description}): {match.group(0)[:80]!r}"
            )


def embed_json(payload: dict) -> str:
    """Serialise the payload so it cannot break out of its <script> block."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _read_assets() -> tuple[str, str]:
    css_parts: list[str] = []
    js_parts: list[str] = []
    for name in ASSET_ORDER:
        path = ASSETS / name
        if not path.is_file():
            raise DashboardBuildError(f"asset not found: {path}")
        text = path.read_text(encoding="utf-8")
        (css_parts if name.endswith(".css") else js_parts).append(text)
    return "\n".join(css_parts), "\n".join(js_parts)


def render_html(payload: dict) -> str:
    """Inline CSS, JS and the payload into the shell. Gate before returning."""
    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise DashboardBuildError(f"payload missing required key(s): {missing}")

    shell_path = ASSETS / "shell.html"
    if not shell_path.is_file():
        raise DashboardBuildError(f"asset not found: {shell_path}")

    css, js = _read_assets()
    html = shell_path.read_text(encoding="utf-8")
    for slot, value in (("{{CSS}}", css), ("{{JS}}", js), ("{{DATA}}", embed_json(payload))):
        if slot not in html:
            raise DashboardBuildError(f"shell.html is missing the {slot} slot")
        html = html.replace(slot, value)

    assert_self_contained(html)
    return html


def build(data_path: Path, out_path: Path) -> str:
    """Read data.json, render, write. Raises DashboardBuildError."""
    data_path = Path(data_path)
    if not data_path.is_file():
        raise DashboardBuildError(f"data payload not found: {data_path}")

    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DashboardBuildError(f"could not parse {data_path}: {exc}") from exc

    html = render_html(payload)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return html


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build output/dashboard.html")
    parser.add_argument("data", nargs="?", default="output/data.json")
    parser.add_argument("out", nargs="?", default="output/dashboard.html")
    args = parser.parse_args(argv)

    try:
        html = build(Path(args.data), Path(args.out))
    except DashboardBuildError as exc:
        print(f"DASHBOARD BUILD FAILED: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {args.out}: {len(html) / 1024:.0f} KB, self-contained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
