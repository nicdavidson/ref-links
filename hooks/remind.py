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
examples, kinds = [], []
if links.REPO:
    examples.append(f"[#1234]({links.gh_url('1234')}) (short label)")
    kinds.append("issue or pull request")
for prefix in links.TRACKERS:
    examples.append(f"[{prefix}-123]({links.item_url(prefix, '123')}) (short label)")
if links.TRACKERS:
    kinds.append(" / ".join(f"{p}-n" for p in links.TRACKERS) + " id")
rule = (
    f"Link rule: the first mention of an {' or '.join(kinds)} in this reply is a link with a 2-5 word label: "
    + ", ".join(examples) + ". "
    + ("Later mentions may be bare #1234, but a tracker id keeps its label. " if links.REPO
       else "Later mentions keep their label. ")
    + f"Ids in code font are exempt. Get the links with: python3 {tool} <number> <PREFIX-n>"
)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": rule}}))
