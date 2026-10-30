#!/usr/bin/env python3
"""UserPromptSubmit: put the link rule in front of the agent before it replies."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import links  # noqa: E402

try:
    cwd = json.load(sys.stdin).get("cwd")
except Exception:
    cwd = None
if not links.applies(cwd):
    sys.exit(0)
tool = Path(__file__).resolve().parent.parent / "bin" / "links"
examples, kinds, notes = [], [], []
if links.REPO:
    examples.append(f"[#1234]({links.gh_url(links.REPO + '#1234')}) (short label)")
    notes.append(f"Bare #123 means {links.REPO}; name any other repository as owner/name#123.")
elif links.AUTO:
    examples.append("[owner/name#1234](https://github.com/owner/name/issues/1234) (short label)")
    notes.append("This folder is not a GitHub checkout, so write issues and pull requests as owner/name#123 "
                 "for the repository under discussion.")
if links.REPO or links.AUTO:
    kinds.append("issue or pull request")
for prefix in links.TRACKERS:
    examples.append(f"[{prefix}-123]({links.item_url(prefix, '123')}) (short label)")
if links.TRACKERS:
    kinds.append(" / ".join(f"{p}-n" for p in links.TRACKERS) + " id")
rule = (
    f"Link rule: the first mention of an {' or '.join(kinds)} in this reply is a link with a 2-5 word label: "
    + ", ".join(examples) + ". " + " ".join(notes) + " "
    + ("Later mentions of an issue or pull request may be bare, but a tracker id keeps its label. "
       if kinds and kinds[0].startswith("issue") else "Later mentions keep their label. ")
    + f"Ids in code font are exempt. Get the links with: python3 {tool} <owner/name#n or n> <PREFIX-n>"
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": rule}}))
