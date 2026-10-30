"""Run: python3 -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Never touch the real config or label cache; set up a made-up repository and two trackers.
os.environ["XDG_CACHE_HOME"] = tempfile.mkdtemp()
os.environ["XDG_CONFIG_HOME"] = CONFIG_HOME = tempfile.mkdtemp()
Path(CONFIG_HOME, "ref-links").mkdir()
Path(CONFIG_HOME, "ref-links", "config").write_text(
    "# test settings\nREF_LINKS_REPO=example-org/example-repo\n"
    "REF_LINKS_ITEMS=ABC=https://acme.atlassian.net/browse/ABC-{n} ENG=https://linear.app/acme/issue/ENG-{n}\n")
Path(CONFIG_HOME, "ref-links", "items.tsv").write_text("ABC-123\tshort label\tA made-up item\neng-7\tlower key\tAnother\n")
for key in [k for k in os.environ if k.startswith("REF_LINKS_")]:
    del os.environ[key]
sys.path.insert(0, str(ROOT / "hooks"))
import links  # noqa: E402

ABC = "https://acme.atlassian.net/browse/ABC-640"
PR = "https://github.com/example-org/example-repo/pull/1210"
ISSUE = "https://github.com/example-org/example-repo/issues/88"
NO_GH = {**os.environ, "PATH": "/usr/bin:/bin", "REF_LINKS_ALWAYS": "1"}
NO_GH["PATH"] = os.pathsep.join(p for p in NO_GH["PATH"].split(os.pathsep) if not (Path(p) / "gh").exists())


class ItemRule(unittest.TestCase):
    def test_link_then_labelled_mentions_pass(self):
        self.assertEqual(links.item_problems(f"[ABC-640]({ABC}) (validator reasons), then ABC-640 (validator reasons)."), [])

    def test_bold_link_and_quoted_title_count_as_labelled(self):
        self.assertEqual(links.item_problems(f"**[ABC-640]({ABC})** (validator reasons)"), [])
        self.assertEqual(links.item_problems(f'[ABC-640]({ABC}), titled "Follow-on: every managed run"'), [])

    def test_missing_label_or_link_is_named(self):
        self.assertEqual(links.item_problems(f"[ABC-640]({ABC}) and more"), [("ABC-640", "no label")])
        self.assertEqual(links.item_problems("ABC-640 (validator reasons)"), [("ABC-640", "first mention has no link")])
        self.assertEqual(links.item_problems("see ABC-637 and ENG-653"), [("ABC-637", "no label"), ("ENG-653", "no label")])

    def test_each_tracker_is_its_own_id(self):
        self.assertEqual(links.item_problems("ABC-1 (x) ENG-1 (y)"),
                         [("ABC-1", "first mention has no link"), ("ENG-1", "first mention has no link")])

    def test_unknown_prefixes_urls_and_names_are_not_mentions(self):
        self.assertEqual(links.item_problems(f"see {ABC}, [the item]({ABC}), feat/ABC-640-x, XABC-640, UTF-8, ISO-9001"), [])

    def test_code_is_exempt(self):
        for code in ("`feat/ABC-640`", "```\nABC-640\n```", "~~~\nABC-640\n~~~", "text\n\n    ABC-640 indented\n"):
            self.assertEqual(links.item_problems(code), [], code)
        self.assertEqual(links.item_problems("ABC-640"), [("ABC-640", "no label")])

    def test_url_template(self):
        self.assertEqual(links.item_url("eng", "5"), "https://linear.app/acme/issue/ENG-5")


class GitHubRule(unittest.TestCase):
    def test_link_with_label_then_bare_passes(self):
        self.assertEqual(links.gh_problems(f"[#1210]({PR}) (HTTP API), then #1210 again."), [])
        self.assertEqual(links.gh_problems(f"[#88]({ISSUE}) (login bug)"), [])

    def test_bare_or_unlabelled_first_mention_is_named(self):
        self.assertEqual(links.gh_problems("see #1210 and #88"),
                         [("example-org/example-repo#1210", "first mention has no link"), ("example-org/example-repo#88", "first mention has no link")])
        self.assertEqual(links.gh_problems(f"[#1210]({PR}) is ready"), [("example-org/example-repo#1210", "no label")])
        self.assertEqual(links.gh_problems(f"| [#1207]({PR}) | (run listing) |"), [("example-org/example-repo#1207", "no label")])

    def test_other_repositories_by_name(self):
        self.assertEqual(links.gh_problems("see acme/tool#5 and acme/tool#5 again"),
                         [("acme/tool#5", "first mention has no link")])
        self.assertEqual(links.gh_problems("[acme/tool#5](https://github.com/acme/tool/pull/5) (fix login)"), [])
        self.assertEqual(links.display("acme/tool#5"), "acme/tool#5")
        self.assertEqual(links.display("example-org/example-repo#5"), "#5")
        self.assertEqual(links.gh_url("acme/tool#5"), "https://github.com/acme/tool/issues/5")

    def test_not_references(self):
        for text in ("x#1210", "a/#1210", "&#1234;", "##123 heading", "https://e.com/?#1234", "page?x=#1234",
                     "use color #333", "colour #333", "`#1210`"):
            self.assertEqual(links.gh_problems(text), [], text)

    def test_label_drops_the_tracker_tag_and_keeps_five_words(self):
        self.assertEqual(links.short_label("[ABC-123] A person signs in to the server with a work account"), "A person signs in to")
        self.assertEqual(links.short_label("Serve reads once (ENG-775)"), "Serve reads once")


def transcript(*entries) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as t:
        for e in entries:
            t.write((e if isinstance(e, str) else json.dumps(e)) + "\n")
    return t.name


def said(role: str, text, **extra) -> dict:
    return {"type": role, "message": {"content": [{"type": "text", "text": text}]}, **extra}


class Hooks(unittest.TestCase):
    def setUp(self):
        links.CACHE.mkdir(parents=True, exist_ok=True)
        links.GH_TITLES.write_text(f"example-org/example-repo#1210\tHTTP API\tServe operations over HTTP\t{PR}\n"
                                   f"example-org/example-repo#88\tlogin bug\tLogin fails\t{ISSUE}\nexample-org/example-repo#000\t\t\t\n"
                                   "acme/tool#5\tfix login\tFix login\thttps://github.com/acme/tool/pull/5\n",
                                   encoding="utf-8")

    def run_check(self, hook: dict, env=None) -> str:
        ran = subprocess.run([sys.executable, str(ROOT / "hooks/check.py")], input=json.dumps(hook),
                             capture_output=True, text=True, env=env or NO_GH)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stderr, "")
        return ran.stdout

    def test_reads_the_reply_from_the_hook_before_the_transcript(self):
        path = transcript(said("user", "status?"))
        out = json.loads(self.run_check({"transcript_path": path, "last_assistant_message": "#1210 merged, #88 fixed"}))
        self.assertIn(f"[#1210]({PR}) (HTTP API)", out["systemMessage"])
        self.assertIn(f"[#88]({ISSUE}) (login bug)", out["systemMessage"])

    def test_transcript_fallback_skips_tool_results_and_meta_entries(self):
        tool_result = {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}}
        path = transcript(said("user", "status?"), said("assistant", "#1210 is open."), tool_result,
                          said("user", "skill body", isMeta=True), said("assistant", "Done."))
        self.assertIn("#1210", json.loads(self.run_check({"transcript_path": path}))["systemMessage"])
        path = transcript(said("assistant", "#1210 is open."), said("user", "next?"), said("assistant", "Done."))
        self.assertEqual(self.run_check({"transcript_path": path}), "")

    def test_clean_reply_says_nothing(self):
        self.assertEqual(self.run_check({"last_assistant_message": f"[#1210]({PR}) (HTTP API) merged."}), "")

    def test_known_labels_show_a_key_without_blocking(self):
        out = json.loads(self.run_check({"last_assistant_message": "#1210 merged, ABC-123 next"}))
        self.assertNotIn("decision", out)
        self.assertIn("[ABC-123](https://acme.atlassian.net/browse/ABC-123) (short label)", out["systemMessage"])

    def test_a_number_github_has_nothing_for_is_ignored(self):
        self.assertEqual(self.run_check({"last_assistant_message": "black is #000"}), "")

    def test_unknown_label_blocks_once(self):
        out = json.loads(self.run_check({"last_assistant_message": "ENG-9 merged"}))
        self.assertEqual(out["decision"], "block")
        self.assertIn("(?)", out["reason"])
        self.assertEqual(self.run_check({"last_assistant_message": "ENG-9 merged", "stop_hook_active": True}), "")

    def test_off_outside_the_owners_checkouts(self):
        env = {k: v for k, v in NO_GH.items() if k != "REF_LINKS_ALWAYS"}
        self.assertEqual(self.run_check({"last_assistant_message": "#99999", "cwd": tempfile.mkdtemp()}, env), "")
        ran = subprocess.run([sys.executable, str(ROOT / "hooks/remind.py")], input=json.dumps({"cwd": tempfile.mkdtemp()}),
                             capture_output=True, text=True, env=env)
        self.assertEqual((ran.returncode, ran.stdout), (0, ""))

    def test_on_in_a_checkout_of_the_owner(self):
        repo = tempfile.mkdtemp()
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "remote", "add", "origin", "git@github.com:Example-Org/other.git"], check=True)
        bin_dir = tempfile.mkdtemp()  # git but no gh: NO_GH's PATH may have dropped git with gh
        os.symlink(shutil.which("git"), Path(bin_dir, "git"))
        env = {**{k: v for k, v in NO_GH.items() if k != "REF_LINKS_ALWAYS"}, "PATH": bin_dir}
        self.assertIn("ENG-9", self.run_check({"last_assistant_message": "ENG-9", "cwd": repo}, env))

    def test_trackers_only_is_on_everywhere(self):
        cfg = tempfile.mkdtemp()
        Path(cfg, "ref-links").mkdir()
        Path(cfg, "ref-links", "config").write_text("REF_LINKS_ITEMS=OPS=https://t.example/OPS-{n}\n")
        env = {**{k: v for k, v in NO_GH.items() if k != "REF_LINKS_ALWAYS"}, "XDG_CONFIG_HOME": cfg}
        out = json.loads(self.run_check({"last_assistant_message": "OPS-4 and #12", "cwd": tempfile.mkdtemp()}, env))
        self.assertIn("[OPS-4](https://t.example/OPS-4)", out["reason"])
        self.assertNotIn("#12", out["reason"])  # no repository: numbers are not references

    def auto_env(self, cwd_remote=None):
        cfg, bin_dir = tempfile.mkdtemp(), tempfile.mkdtemp()
        Path(cfg, "ref-links").mkdir()
        Path(cfg, "ref-links", "config").write_text("REF_LINKS_REPO=auto\n")
        os.symlink(shutil.which("git"), Path(bin_dir, "git"))
        cwd = tempfile.mkdtemp()
        if cwd_remote:
            subprocess.run(["git", "init", "-q", cwd], check=True)
            subprocess.run(["git", "-C", cwd, "remote", "add", "origin", cwd_remote], check=True)
        env = {**{k: v for k, v in NO_GH.items() if k != "REF_LINKS_ALWAYS"}, "XDG_CONFIG_HOME": cfg, "PATH": bin_dir}
        return env, cwd

    def test_auto_uses_the_checkouts_repository(self):
        env, cwd = self.auto_env("https://github.com/acme/tool.git")
        out = json.loads(self.run_check({"last_assistant_message": "#5 merged", "cwd": cwd}, env))
        self.assertIn("[#5](https://github.com/acme/tool/pull/5) (fix login)", out["systemMessage"])

    def test_auto_outside_a_checkout_takes_named_references_only(self):
        env, cwd = self.auto_env()
        self.assertEqual(self.run_check({"last_assistant_message": "#5 is the #1 priority", "cwd": cwd}, env), "")
        out = json.loads(self.run_check({"last_assistant_message": "acme/tool#5 merged", "cwd": cwd}, env))
        self.assertIn("[acme/tool#5](https://github.com/acme/tool/pull/5) (fix login)", out["systemMessage"])
        ran = subprocess.run([sys.executable, str(ROOT / "hooks/remind.py")], input=json.dumps({"cwd": cwd}),
                             capture_output=True, text=True, env=env)
        self.assertIn("owner/name#123", json.loads(ran.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_bad_input_never_fails_the_session(self):
        path = transcript("not json", {"type": "assistant", "message": "oops"},
                          {"type": "assistant", "message": {"content": [{"type": "text", "text": None}]}}, said("assistant", "ABC-1"))
        for hook in ({}, {"transcript_path": "/nonexistent/t.jsonl"}, {"transcript_path": path}):
            self.run_check(hook)
        ran = subprocess.run([sys.executable, str(ROOT / "hooks/check.py")], input="not json", capture_output=True, text=True, env=NO_GH)
        self.assertEqual((ran.returncode, ran.stderr), (0, ""))

    def test_reminder_names_the_links_command_and_each_tracker(self):
        ran = subprocess.run([sys.executable, str(ROOT / "hooks/remind.py")], input="{}", capture_output=True, text=True, env=NO_GH)
        context = json.loads(ran.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(ROOT / "bin/links"), context)
        self.assertIn("ABC-123", context)
        self.assertIn("ENG-123", context)

    def test_links_prints_each_kind_and_refuses_unknown(self):
        ran = subprocess.run([sys.executable, str(ROOT / "bin/links"), "1210", "#88", "abc-123", "ENG-7", "000", "ZZZ-1"],
                             capture_output=True, text=True, env=NO_GH)
        self.assertEqual(ran.stdout.splitlines(), [
            f"[#1210]({PR}) (HTTP API)",
            f"[#88]({ISSUE}) (login bug)",
            "[ABC-123](https://acme.atlassian.net/browse/ABC-123) (short label)",
            "[ENG-7](https://linear.app/acme/issue/ENG-7) (lower key)",
        ])
        self.assertIn("GitHub has no such issue or pull request", ran.stderr)
        self.assertIn("ZZZ-1: not an issue reference or a known tracker id", ran.stderr)

    def test_does_nothing_until_set_up(self):
        env = {**NO_GH, "XDG_CONFIG_HOME": tempfile.mkdtemp()}
        self.assertEqual(self.run_check({"last_assistant_message": "#99999 ABC-1"}, env), "")
        ran = subprocess.run([sys.executable, str(ROOT / "hooks/remind.py")], input="{}", capture_output=True, text=True, env=env)
        self.assertEqual((ran.returncode, ran.stdout), (0, ""))
        ran = subprocess.run([sys.executable, str(ROOT / "bin/links"), "1210"], capture_output=True, text=True, env=env)
        self.assertEqual(ran.returncode, 1)
        self.assertIn("not set up", ran.stderr)


if __name__ == "__main__":
    unittest.main()
