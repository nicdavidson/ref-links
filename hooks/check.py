#!/usr/bin/env python3
"""Stop: check the reply for issues, pull requests and tracker items without a link and label.

When every missing label is known, it shows the person a one-line key and lets the reply stand
(another model turn would re-read the whole context). When a label is unknown, it blocks the
stop once so the agent can post the key itself. Never blocks twice in a row, and never fails
the session: any error ends the check quietly.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import links  # noqa: E402

LOOKUP_SECONDS = 15  # gh lookups stop after this; the hook's own timeout is 30


def last_reply(hook: dict) -> str:
    """The reply just written: the hook's own copy, else the assistant text in the transcript since the last prompt."""
    if isinstance(hook.get("last_assistant_message"), str):
        return hook["last_assistant_message"]
    texts = []
    for line in reversed(Path(hook["transcript_path"]).read_text(encoding="utf-8").splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if entry.get("type") == "user" and not entry.get("isMeta"):
            blocks = content if isinstance(content, list) else [{"type": "text"}]
            if any(isinstance(b, dict) and b.get("type") == "text" for b in blocks):
                break
        elif entry.get("type") == "assistant" and isinstance(content, list):
            texts.extend(b["text"] for b in reversed(content)
                         if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str))
    return "\n".join(reversed(texts))


def verdict(reply: str) -> dict | None:
    items, refs = links.item_problems(reply), links.gh_problems(reply)
    if not items and not refs:
        return None
    deadline = time.monotonic() + LOOKUP_SECONDS
    lines, unknown = [], False
    for ref, issue in dict.fromkeys(items):
        label = links.item_label(ref) or "?"
        unknown |= label == "?"
        prefix, number = ref.split("-", 1)
        lines.append(f"[{ref}]({links.item_url(prefix, number)}) ({label}) [{issue}]")
    for number, issue in dict.fromkeys(refs):
        label = links.gh_label(number, deadline)
        if label == links.NOT_FOUND:
            continue  # GitHub has no such issue or pull request: a number, not a reference
        if label is None:
            label, unknown = "?", True
        lines.append(f"[#{number}]({links.gh_url(number)}) ({label}) [{issue}]")
    if not lines:
        return None
    if unknown:
        return {"decision": "block", "reason": (
            "Link rule: the reply above names issues, pull requests or tracker items without a link on first "
            "mention or without a short label. Post a one-line key with each as a link plus a 2-5 word label; "
            "write your own label where it shows (?):\n" + "\n".join(lines))}
    return {"systemMessage": "Key: " + "; ".join(lines)}


def main() -> int:
    try:
        hook = json.load(sys.stdin)
        if hook.get("stop_hook_active") or not links.applies(hook.get("cwd")):
            return 0
        out = verdict(last_reply(hook))
    except Exception:
        return 0
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
