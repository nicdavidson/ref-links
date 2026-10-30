# ref-links

A Claude Code plugin that makes Claude link every GitHub issue, pull request and tracker item it mentions, with a short label. You click through, and you never have to remember what each number was.

Claude writes `#1234 (short label)` or `owner/name#1234 (short label)` as a link to the issue or pull request on GitHub, and `ABC-123 (short label)` as a link to the item in your tracker: Jira, Linear, Plane, YouTrack, or anything with a URL per id.

With `REF_LINKS_REPO=auto`, `#1234` means the repository of the checkout you are in, and outside a checkout Claude names the repository it is talking about (`owner/name#1234`).

## Install

Paste this to Claude Code:

> Install the ref-links plugin: run `claude plugin marketplace add nicdavidson/ref-links` and `claude plugin install ref-links@ref-links`, then set it up by following the plugin's `skills/setup/SKILL.md`.

Claude installs it, finds your repository and tracker addresses from your checkout, your `gh` sign-in and any connected tracker, shows you what it found, and writes the config. To set it up again later, run `/ref-links:setup`.

It needs `python3` (3.9 or later). It uses `gh` to read issue and pull request titles; without `gh`, Claude writes its own labels.

## What it does

| Piece | When | What |
|--|--|--|
| `hooks/remind.py` | Before each reply (UserPromptSubmit) | Adds the rule and an example to Claude's context, with the path to `bin/links`. |
| `hooks/check.py` | After each reply (Stop) | Finds issues, pull requests and tracker ids whose first mention has no link, or that have no label. When it knows every label, it shows you a one-line key and lets the reply stand. When a label is unknown, it sends Claude back once to post the key itself. It never sends it back twice in a row. |
| `bin/links` | When Claude runs it | `links 1234 owner/name#56 ABC-123` prints each link with its label. |

The rule: the first mention of an issue, pull request or tracker id in a reply is a link with a 2-5 word label. Later mentions of an issue or pull request may be bare (`#1234`); a tracker id keeps its label (`ABC-123 (short label)`). Anything in code font, such as a branch name, is exempt. A bare `#1234` counts as a reference only where the repository is known (a fixed `REF_LINKS_REPO`, or a GitHub checkout with `auto`); `owner/name#1234` counts everywhere.

## Settings

The setup writes `~/.config/ref-links/config`. To write it by hand:

```
REF_LINKS_REPO=auto
REF_LINKS_ITEMS=ABC=https://acme.atlassian.net/browse/ABC-{n} ENG=https://linear.app/acme/issue/ENG-{n}
```

| Setting | What | Default |
|--|--|--|
| `REF_LINKS_REPO` | `auto` (the current checkout's GitHub repository), or a fixed `owner/name` that `#123` numbers belong to | none |
| `REF_LINKS_ITEMS` | Tracker prefixes and URL templates, space separated; `{n}` is the number | none |
| `REF_LINKS_ALWAYS` | `1` to use the rule in every folder | unset |

Set at least one of the first two. With `auto` or only trackers, the rule is on everywhere. With a fixed repository, it is on in checkouts of repositories under that repository's owner. An environment variable of the same name overrides the file.

## Labels

- Issues and pull requests: the first five words of the GitHub title, read with `gh` the first time and cached in `~/.cache/ref-links/github-refs.tsv` (one row per `owner/name#n`). Edit a row there to change a label. A reference GitHub has nothing for (`#000`) is cached as such and ignored.
- Tracker items: `~/.config/ref-links/items.tsv`, one row per item: the id (`ABC-123`), a short label, and the title, separated by tabs. A missing item shows `(?)`, and Claude writes its own label.

## Notes

- Links open with a click, or Ctrl/Cmd-click, in terminals that support them.
- The check reads only the text of Claude's last reply. It sends nothing anywhere except `gh` lookups of titles.

## Development

```
python3 -m unittest discover -s tests
claude plugin validate .
```
