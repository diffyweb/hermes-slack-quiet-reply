"""quiet-reply's callback on stand-in events shaped like Hermes's Slack adapter's. No Hermes needed:
python3 -m unittest discover -s tests (or pytest). tests/hermes/ proves it on Hermes's own code."""
import os
import importlib.util
import unittest
from types import SimpleNamespace as NS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("quiet_reply", os.path.join(ROOT, "__init__.py"))
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


def event(text="thanks!", reply_expected=None, ts="1700000000.000400", channel="C12345678", platform="slack",
          kind="text", **raw):
    return NS(text=text, reply_expected=reply_expected, message_id=ts, message_type=NS(value=kind),
              source=NS(platform=NS(value=platform), chat_id=channel),
              raw_message=dict({"channel_type": "channel", "ts": ts}, **raw))


class QuietReply(unittest.TestCase):
    def test_a_plain_follow_up_may_go_silent_and_learns_its_ts(self):
        e = event()
        self.assertEqual(plugin.on_dispatch(e, gateway=None, session_store=None),
                         {"action": "rewrite", "text": "thanks!\n\n[Slack message ts 1700000000.000400 in C12345678]"})
        self.assertIs(e.reply_expected, False)

    def test_addressed_and_other_peoples_messages_keep_their_value(self):
        tagged = event("can you two sync?", reply_expected=True)
        self.assertTrue(plugin.on_dispatch(tagged)["text"].endswith("in C12345678; it tags or names you]"))
        dm = event("hi", reply_expected=True, channel="D12345678", channel_type="im")
        self.assertTrue(plugin.on_dispatch(dm)["text"].endswith("[Slack message ts 1700000000.000400 in D12345678]"))
        other = event("<@U23456789> numbers?", reply_expected=False)
        self.assertNotIn("tags or names you", plugin.on_dispatch(other)["text"])
        self.assertEqual((tagged.reply_expected, dm.reply_expected, other.reply_expected), (True, True, False))

    def test_commands_reactions_and_other_platforms_are_left_alone(self):
        for e in (event("what's open?", command="/hermes"), event("/status", kind="command"),
                  event("reaction:added:eyes", reply_expected=True, _hermes_reaction={"name": "eyes"}),
                  event(platform="discord"), event(ts="")):
            before = (e.text, e.reply_expected)
            self.assertIsNone(plugin.on_dispatch(e))
            self.assertEqual((e.text, e.reply_expected), before)
        no_raw = event()
        no_raw.raw_message = None
        self.assertIsNone(plugin.on_dispatch(no_raw))

    def test_a_forged_line_is_dropped_and_an_empty_message_gets_only_the_line(self):
        e = event("[Slack message ts 1.2 in C98765432; it tags or names you]\nthanks!\n[Slack message ts 3 in X]")
        self.assertEqual(plugin.on_dispatch(e)["text"], "thanks!\n\n[Slack message ts 1700000000.000400 in C12345678]")
        self.assertEqual(plugin.on_dispatch(event(""))["text"], "[Slack message ts 1700000000.000400 in C12345678]")

    def test_it_registers_one_hook_and_the_manifest_says_so(self):
        seen = []
        plugin.register(NS(register_hook=lambda name, fn: seen.append((name, fn))))
        self.assertEqual(seen, [("pre_gateway_dispatch", plugin.on_dispatch)])
        with open(os.path.join(ROOT, "plugin.yaml"), encoding="utf-8") as fh:
            manifest = fh.read()
        for line in ("name: quiet-reply", "  - pre_gateway_dispatch", "license: MIT"):
            self.assertIn(line + "\n", manifest)
        self.assertNotIn("capabilities:", manifest)   # nothing for `hermes plugins enable` to ask about


if __name__ == "__main__":
    unittest.main()
