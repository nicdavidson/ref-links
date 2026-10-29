---
name: setup
description: Set up the ref-links plugin for this person, writing its config file and tracker labels. Use when someone asks to set up, configure, or repair ref-links, or right after installing it.
---

# Set up ref-links

ref-links needs at least one of two values in `~/.config/ref-links/config` before its hooks do anything. The plugin ships no addresses, so find them on this person's machine and accounts, and ask only for what you cannot find. Show the person each value you found and where it came from before you write anything.

## 1. The GitHub repository: `REF_LINKS_REPO`

The repository that bare `#123` numbers belong to, as `owner/name`. Optional: leave it out if the person only wants tracker links.
- If the current folder is a git checkout, run `gh repo view --json nameWithOwner -q .nameWithOwner`.
- Otherwise ask which checkout holds the main repository, and run it there.
- If `gh` is missing or not signed in, say so: issue and pull request labels need it (`gh auth login`).

## 2. Trackers: `REF_LINKS_ITEMS`

One `PREFIX=URL` pair per tracker, space separated, with `{n}` where the number goes. Optional.

| Tracker | Template |
|--|--|
| Jira | `ABC=https://<site>.atlassian.net/browse/ABC-{n}` |
| Linear | `ENG=https://linear.app/<workspace>/issue/ENG-{n}` |
| Plane | `ABC=https://app.plane.so/<workspace>/browse/ABC-{n}/` |
| YouTrack | `ABC=https://<site>.youtrack.cloud/issue/ABC-{n}` |

- If a tracker tool (Jira, Linear, Plane) is connected, read the site or workspace and the project keys from it.
- Otherwise look for a tracker link the person already has: the checkout's files (`git grep -h -o -E 'https://[^ )"]*/(browse|issue)/[A-Z][A-Z0-9]*-[0-9]+'`), its history (`git log --all --format=%B | grep -o -E 'https://[^ )"]*/(browse|issue)/[A-Z][A-Z0-9]*-[0-9]+' | head`), then recent pull request bodies (`gh pr list --state all --limit 100 --json body`). Replace the number with `{n}`.
- Otherwise ask the person to open any item and paste its address.

## 3. Write the config

```
mkdir -p ~/.config/ref-links
```

Write `~/.config/ref-links/config`:

```
REF_LINKS_REPO=<owner/name>
REF_LINKS_ITEMS=<PREFIX=URL with {n}> <PREFIX=URL with {n}>
```

If the file exists, show the person what would change and ask before you replace it.

## 4. Tracker labels (optional)

Labels for tracker items live in `~/.config/ref-links/items.tsv`, one row per item: the id (`ABC-123`), a 2-5 word label, and the title, separated by tabs. Without a row, Claude writes its own label, so this only makes labels steadier.
- If a tracker tool is connected, list the open items of each configured project and write one row each. Write each label yourself: 2-5 plain words naming what the item is about.
- Keep rows the person already has; add only missing ids.
- Without a tracker tool, skip this step and say so.

## 5. Check it

Find the plugin's `bin/links` (`find ~/.claude/plugins -path '*ref-links*/bin/links'`) and run it with a recent issue or pull request number and a tracker id, for example `python3 <path>/bin/links <number> <PREFIX>-<n>`. Each should print as a link with a label. Show the person the output.

Tell them where the rule is on: in checkouts of repositories under the configured repository's owner (everywhere when only trackers are set, or with `REF_LINKS_ALWAYS=1`). The hooks read the config on every reply, so it takes effect at once; only a plugin installed during this session needs `/reload-plugins` or a new session before its hooks run.
