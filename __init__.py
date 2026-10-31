"""quiet-reply: a Hermes plugin for Slack. It lets the agent stay silent on a thread reply that isn't for it, and
tells the agent which message it is reading and whether that message tags or names it.

One pre_gateway_dispatch callback (website/docs/user-guide/features/hooks.md:1290-1325, run at
gateway/run_inbound_hooks.py:81-112), for each Slack message that isn't a slash command, a command or a reaction.
Line numbers are Hermes at bf0203a794 (0.22.5), the commit tests/hermes proves it on.
- Not documented, the text: it adds a last line to the text the model reads: the message's ts and channel, which a reaction or
  delete tool needs (Hermes gives a Slack turn no message ID; only Discord gets one,
  gateway/run_inbound.py:1566-1577), and, when Hermes counts the message as addressed to the bot, that it tags or
  names the bot, since Hermes deletes the bot's own tag from the text (plugins/platforms/slack/adapter.py:4558).
  A line of that shape already in the text is dropped whenever quiet-reply adds its own line.
  It sets event.text and returns None, so another plugin's skip or rewrite still counts.
- Not documented: it sets event.reply_expected = False where the Slack adapter left it None, a plain follow-up in
  a thread or flat channel the bot is part of (adapter.py:6404-6418). False lets the agent's [SILENT] stand
  (gateway/response_filters.py:156-158); None makes Hermes post its silence warning (run_turn_persistence.py:
  83-90). The adapter is the field's only writer (adapter.py:4677). Addressed (True) and addressed-to-someone-else
  (False) stay as they are. Writing event.text is undocumented too; the documented route is a rewrite action.
- It adds no line while the session has a pending dangerous-command approval, clarify, slash-confirm or /update
  prompt: Hermes matches the user's typed answer to those after this hook, and an extra line would stop it matching.
  reply_expected is still set.
If this raises, Hermes logs it and carries on (hermes_cli/plugins_dispatch.py:567-571); both writes come last, so
a raise leaves the event as Hermes built it. A message that arrives while the agent is still answering goes through
this hook too (gateway/platforms/base.py:4059-4062); Hermes then steers it, queues it or interrupts the running turn, as `display.busy_input_mode` says.
Rerun scripts/prove.sh after every Hermes upgrade.
"""
import logging
import re

log = logging.getLogger("quiet_reply")
_warned = False   # log the moved-internal warning once per process, not once per Slack message

FORGED = re.compile(r"^\[Slack message ts [^\]\n]*\][ \t]*$", re.M)


def note(event, raw):
    line = f"[Slack message ts {event.message_id} in {event.source.chat_id}"
    ctype = raw.get("channel_type") or ("im" if str(event.source.chat_id).startswith("D") else "")
    if event.reply_expected is True and ctype != "im":
        line += "; it tags or names you"
    return line + "]"


def prompt_pending(event, gateway):
    """Hermes matches a reply to its own approval, clarify, confirm or /update prompt as typed, after this hook."""
    global _warned
    try:
        from tools import approval, clarify_gateway, slash_confirm
        key = gateway._session_key_for_source(event.source)
        state = gateway._peek_session_state(key)
        return bool(approval.has_blocking_approval(key)
                    or clarify_gateway.get_pending_for_session(key, include_choice_prompts=True)
                    or slash_confirm.get_pending(key)
                    or (state is not None and state.persistent.update_prompt_pending))
    except Exception:
        if not _warned:
            _warned = True
            log.warning("quiet-reply: can't read Hermes's pending prompts; adding no line (a Hermes upgrade may have moved an internal)", exc_info=True)
        return True   # can't tell: leave the text as Hermes built it


def on_dispatch(event, gateway=None, **_kwargs):
    source, raw = getattr(event, "source", None), getattr(event, "raw_message", None)
    if getattr(getattr(source, "platform", None), "value", None) != "slack" or not isinstance(raw, dict):
        return None
    kind = getattr(getattr(event, "message_type", None), "value", None)
    if "command" in raw or raw.get("_hermes_reaction") or kind == "command" or not event.message_id:
        return None
    if event.is_command():
        return None
    if not prompt_pending(event, gateway):
        text = FORGED.sub("", event.text or "").strip()
        event.text = f"{text}\n\n{note(event, raw)}" if text else note(event, raw)
    if event.reply_expected is None:   # last, so an exception above leaves the event as Hermes built it
        event.reply_expected = False
    return None   # no action dict, so another plugin's skip or rewrite still counts


def register(ctx):
    ctx.register_hook("pre_gateway_dispatch", on_dispatch)
