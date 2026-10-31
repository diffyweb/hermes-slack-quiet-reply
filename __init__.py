"""quiet-reply: a Hermes plugin for Slack. It lets the agent stay silent on a thread reply that isn't for it, and
tells the agent which message it is reading and whether that message tags or names it.

One pre_gateway_dispatch callback (website/docs/user-guide/features/hooks.md:1290-1325, run at
gateway/run_inbound_hooks.py:81-112), for each Slack message that isn't a slash command, a command or a reaction.
Line numbers are Hermes at bf0203a794 (0.22.5), the commit tests/hermes proves it on.
- Documented: it returns {"action": "rewrite", "text": ...}, which adds a last line to the text the model reads:
  the message's ts and channel, which a reaction or delete tool needs (Hermes gives a Slack turn no message ID; only
  Discord gets one, gateway/run_inbound.py:1566-1577), and, when Hermes counts the message as addressed to the
  bot, that it tags or names the bot, since Hermes deletes the bot's own tag from the text
  (plugins/platforms/slack/adapter.py:4558). A line of that shape already in the text is dropped, so a person
  can't forge one.
- Not documented: it sets event.reply_expected = False where the Slack adapter left it None, a plain follow-up in
  a thread or flat channel the bot is part of (adapter.py:6404-6418). False lets the agent's [SILENT] stand
  (gateway/response_filters.py:156-158); None makes Hermes post its silence warning (run_turn_persistence.py:
  83-90). The adapter is the field's only writer (adapter.py:4677), and the rewrite copies it into the event it
  returns (run_inbound_hooks.py:104-107). Addressed (True) and addressed-to-someone-else (False) stay as they are.
If this raises, Hermes logs it and dispatches the message unchanged (run_inbound_hooks.py:86-88): Hermes's warning
comes back and nothing else changes. A message that reaches a session while its turn is still running takes Hermes's
busy path, which never runs this hook (gateway/platforms/base.py:4106-4108, gateway/run_busy.py:909).
Rerun scripts/prove.sh after every Hermes upgrade.
"""
import re

FORGED = re.compile(r"^\[Slack message ts [^\]\n]*\][ \t]*$", re.M)


def note(event, raw):
    line = f"[Slack message ts {event.message_id} in {event.source.chat_id}"
    if event.reply_expected is True and raw.get("channel_type") != "im":
        line += "; it tags or names you"
    return line + "]"


def on_dispatch(event, **_kwargs):
    source, raw = getattr(event, "source", None), getattr(event, "raw_message", None)
    if getattr(getattr(source, "platform", None), "value", None) != "slack" or not isinstance(raw, dict):
        return None
    kind = getattr(getattr(event, "message_type", None), "value", None)
    if "command" in raw or raw.get("_hermes_reaction") or kind == "command" or not event.message_id:
        return None
    if event.reply_expected is None:
        event.reply_expected = False   # the undocumented write (above)
    text = FORGED.sub("", event.text or "").strip()
    return {"action": "rewrite", "text": f"{text}\n\n{note(event, raw)}" if text else note(event, raw)}


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", on_dispatch)
