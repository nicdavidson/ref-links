"""Shared by the hooks and bin/links: where references link to, their labels, and the rule check.

Settings come from ~/.config/ref-links/config (KEY=value lines); the environment overrides them:
  REF_LINKS_REPO    GitHub repository that bare #123 numbers belong to, as owner/name
  REF_LINKS_ITEMS   tracker prefixes and URL templates, space separated, {n} is the number:
                    ABC=https://acme.atlassian.net/browse/ABC-{n} OPS=https://linear.app/acme/issue/OPS-{n}
  REF_LINKS_ALWAYS  1 to apply the rule in every folder, not only in checkouts of the repository's owner
The rule is on once REF_LINKS_REPO or REF_LINKS_ITEMS is set.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "ref-links"
CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ref-links"
ITEM_TITLES = CONFIG_DIR / "items.tsv"
GH_TITLES = CACHE / "github-titles.tsv"


def _settings() -> dict[str, str]:
    found = {}
    try:
        for line in (CONFIG_DIR / "config").read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.strip().startswith("#"):
                found[key.strip()] = value.strip()
    except OSError:
        pass
    found.update({k: v for k, v in os.environ.items() if k.startswith("REF_LINKS_")})
    return found


SETTINGS = _settings()
REPO = SETTINGS.get("REF_LINKS_REPO", "").strip("/")
REPO = REPO if REPO.count("/") == 1 else ""
TRACKERS = {p.upper(): url for p, _, url in (pair.partition("=") for pair in SETTINGS.get("REF_LINKS_ITEMS", "").split())
            if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", p) and url.startswith("http") and "{n}" in url}
CONFIGURED = bool(REPO or TRACKERS)

# A label is a short one in parentheses, or the full title in quotes, optionally after ", titled".
LABEL = r"[*_]{0,2}\s*\(|[*_]{0,2},?\s*(?:titled\s+)?[\"“]"
_PREFIXES = "|".join(sorted(map(re.escape, TRACKERS), key=len, reverse=True)) or r"(?!x)x"
ITEM_MENTION = re.compile(
    rf"\[(?P<lp>{_PREFIXES})-(?P<ln>\d+)\]\(https?://[^)\s]*\)(?P<ll>{LABEL})?"
    rf"|(?<![\w/-])(?P<bp>{_PREFIXES})-(?P<bn>\d+)\b(?P<bl>{LABEL})?")
GH_LINK = r"\[#(\d{1,6})\]\(https://github\.com/[^)\s]*/(?:pull|issues)/\d+[^)\s]*\)"
# Not after a word, a path, another # or a URL's ? or =, and not a color written as `color #333`.
GH_MENTION = re.compile(rf"{GH_LINK}({LABEL})?|(?<![\w/\[&#?=])(?<!color )(?<!colour )#(\d{{1,6}})\b")


def item_url(prefix: str, number: str) -> str:
    return TRACKERS[prefix.upper()].replace("{n}", number)


def gh_url(number: str) -> str:
    """Issues and pull requests share numbers; GitHub redirects /issues/n to /pull/n."""
    return GH_KINDS.get(number, f"https://github.com/{REPO}/issues/{number}")


def _prose(text: str) -> str:
    """The text without code blocks and code spans: branch names and commands are exempt."""
    text = re.sub(r"(```|~~~).*?\1", "", text, flags=re.S)
    text = re.sub(r"(?m)^(?: {4}|\t).*$", "", text)
    return re.sub(r"`[^`\n]*`", "", text)


def item_problems(text: str) -> list[tuple[str, str]]:
    """Each (PREFIX-n, what is wrong): every mention needs a label, and the first one a link."""
    seen, found = set(), []
    for m in ITEM_MENTION.finditer(_prose(text)):
        linked = m["ln"] is not None
        ref = f"{(m['lp'] or m['bp']).upper()}-{m['ln'] or m['bn']}"
        labelled = (m["ll"] if linked else m["bl"]) is not None
        if not labelled:
            found.append((ref, "no label"))
        elif not linked and ref not in seen:
            found.append((ref, "first mention has no link"))
        seen.add(ref)
    return found


def gh_problems(text: str) -> list[tuple[str, str]]:
    """Each (number, what is wrong) for an issue or pull request whose first mention is not a link with a label."""
    if not REPO:
        return []
    seen, found = set(), []
    for m in GH_MENTION.finditer(_prose(text)):
        number = m.group(1) or m.group(3)
        if number in seen:
            continue
        seen.add(number)
        if m.group(1) is None:
            found.append((number, "first mention has no link"))
        elif m.group(2) is None:
            found.append((number, "no label"))
    return found


def table(path: Path) -> dict[str, list[str]]:
    """key -> its other columns, from a tab-separated file; # lines are comments."""
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else ():
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) >= 2 and parts[0] and not parts[0].startswith("#"):
            rows.setdefault(parts[0].upper(), parts[1:])
    return rows


def item_label(ref: str) -> str | None:
    row = table(ITEM_TITLES).get(ref.upper())
    return row[0] if row else None


def applies(cwd: str | None) -> bool:
    """On once configured: in a checkout of a repository under REPO's owner, or everywhere with REF_LINKS_ALWAYS=1
    (or when only trackers are set, since there is no owner to match)."""
    if not CONFIGURED:
        return False
    if SETTINGS.get("REF_LINKS_ALWAYS") == "1" or not REPO:
        return True
    owner = "github.com/" + REPO.split("/")[0] + "/"
    try:
        ran = subprocess.run(["git", "-C", cwd or ".", "remote", "-v"], capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return owner.lower() in ran.stdout.replace("git@github.com:", "github.com/").lower()


def short_label(title: str) -> str:
    """A title cut to five words, without a leading [TAG-1] or trailing (TAG-1) tracker tag."""
    title = re.sub(r"^\s*\[[A-Za-z]+-\d+\]\s*|\s*\([A-Za-z]+-\d+\)\s*$", "", title)
    return " ".join(title.split()[:5])


NOT_FOUND = ""  # cached label for a number GitHub has no issue or pull request for


def _kinds() -> dict[str, str]:
    return {k: row[2] for k, row in table(GH_TITLES).items() if len(row) > 2 and row[2]}


GH_KINDS = _kinds()


def gh_label(number: str, deadline: float | None = None) -> str | None:
    """An issue or pull request's label: from the cache, else from gh (then cached). NOT_FOUND when GitHub has none;
    None when it cannot be looked up (no gh, signed out, offline, or past the deadline)."""
    known = table(GH_TITLES).get(number)
    if known is not None:
        return known[0]
    if not REPO or not shutil.which("gh") or (deadline is not None and time.monotonic() > deadline):
        return None
    try:
        ran = subprocess.run(["gh", "api", f"repos/{REPO}/issues/{number}", "--jq", "[.title, .html_url]"],
                             capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if ran.returncode != 0:
        if "Not Found" not in ran.stdout + ran.stderr:
            return None
        label = title = url = NOT_FOUND
    else:
        title, url = json.loads(ran.stdout)
        label = short_label(title)
        GH_KINDS[number] = url
    CACHE.mkdir(parents=True, exist_ok=True)
    with GH_TITLES.open("a", encoding="utf-8") as f:
        f.write(f"{number}\t{label}\t{title}\t{url}\n")
    return label
