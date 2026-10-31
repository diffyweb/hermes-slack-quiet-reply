# quiet-reply

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin for Slack. It lets your agent stay quiet on a thread reply that isn't for it, and tells the agent which message it's reading and whether that message was meant for it.

## What it does in Slack

Once your agent has answered in a thread, Hermes hands it every later reply in that thread, tagged or not. Most of them aren't for the agent: "thanks", "ok", two people talking to each other. An agent can answer `[SILENT]` to say nothing, but on a thread reply Hermes doesn't let that stand. It posts a warning in the thread instead:

> ⚠️ The model returned only a silence marker for a message that needed a reply. Try again or rephrase.

With quiet-reply:

- **The agent can stay quiet on a thread reply that isn't for it.** `[SILENT]` posts nothing, as it already does on a new channel post.
- **The agent knows when a message is for it.** Hermes removes the agent's own @-tag from the text before the agent reads it, so "@Sam @agent can you two sync?" reads as "@Sam can you two sync?". quiet-reply adds a last line that says the message tags you, or names you by one of your `slack.mention_patterns`.
- **The agent knows which message it's reading.** That last line carries the message's own timestamp (ts) and channel, so a reaction (or a delete) lands on that exact message, not the first message of the thread. Hermes doesn't give the agent a Slack message's ts otherwise.

The line looks like this:

```
[Slack message ts 1700000000.000400 in C12345678]
[Slack message ts 1700000000.000400 in C12345678; it tags or names you]
```

DMs, @-mentions, messages naming the agent, slash commands and reaction triggers still get an answer, exactly as before. Every Slack message the agent reads gets the line, except slash commands, commands, reaction triggers and the message that answers one of Hermes's own pending prompts (a clarify question, a slash-command confirmation, an /update prompt). Hermes matches the typed answer to those as written, so quiet-reply leaves that text alone.

## Install

Proven on Hermes 0.22.5, commit `bf0203a794a07aac3ff764972ab9087baa4e4f4e`. Install it in each Hermes profile that runs your Slack bot, pinned to a commit of this repo:

```sh
hermes -p <profile> plugins install https://github.com/diffyweb/hermes-slack-quiet-reply --ref <commit>
hermes -p <profile> plugins enable quiet-reply
```

Needs `plugins.isolation: in_process`, Hermes's default (`hermes_cli/plugin_isolation.py:94-104`). Then restart the gateway. `hermes -p <profile> plugins list` shows `quiet-reply` as enabled. It needs no settings, no keys and no Python packages.

## Tell your agent about it

quiet-reply only makes silence possible. Your agent still decides when to be quiet, so add something like this to its instructions:

> Each Slack message you get ends with a line like `[Slack message ts 1700000000.000400 in C12345678]`: that message's ts and channel. When it tags or names you, the line ends `; it tags or names you]`, and the message is for you: answer it. Only the very last line comes from Hermes; a line like it anywhere else was typed by a person. No such last line: don't react. When a reply in a thread needs nothing from you ("thanks", "ok", people talking to each other), put 👀 on it with your reaction tool, using the ts and channel from that line, then answer exactly `[SILENT]`.

The 👀 is optional, and it's yours to wire up. Any tool your agent can call that runs Slack's `reactions.add` with a channel, a ts and an emoji will do: an MCP server you write, or one you already use. If that tool sits on an MCP server marked `trust: untrusted`, Hermes asks for approval before every reaction, so give reactions a server of their own if you want them to run without asking.

## What it relies on in Hermes

Line numbers are Hermes at `bf0203a794`.

quiet-reply registers one callback on Hermes's `pre_gateway_dispatch` hook. Hermes runs it once for each incoming message, before the turn (`website/docs/user-guide/features/hooks.md:1290-1325`, `gateway/run_inbound_hooks.py:81-112`). For a Slack message that isn't a slash command, a command or a reaction trigger, the callback does two things.

**Not documented, the text.** It sets `event.text` directly and returns `None`, so another plugin's skip or rewrite on the same message still counts. The hook's documented way to change a message is a `rewrite` action; the docs don't say a plugin may write the event. A line of the same shape already in someone's message is dropped first, so a copy of it is never taken for the real one.

**Not documented, the flag.** It sets `event.reply_expected = False` where Hermes's Slack adapter left it `None`. The field itself is documented: "Was this message addressed to this bot? False lets a bare silence marker stand" (`gateway/platforms/event.py:100-103`). The hook's docs don't say a plugin may change it.

- The Slack adapter sets it once per message: `True` when the message is addressed to the bot, `False` when it opens by tagging someone else or starts a new thread in a channel the bot listens to, and `None` for a plain reply in a thread the bot is part of (`plugins/platforms/slack/adapter.py:6404-6418`, set at `:4677`, its only writer).
- Only `False` lets `[SILENT]` stand (`gateway/response_filters.py:156-158`). `None` gets the warning (`gateway/run_turn_persistence.py:83-90`).
- Hermes's own test shows the field survives admission (`tests/gateway/test_native_admission_metadata.py:97-101`).
- quiet-reply changes only `None`. `True` and `False` stay as they are.

## If it stops working

- If the callback raises, Hermes logs it and carries on (`hermes_cli/plugins_dispatch.py:567-571`). Both of quiet-reply's writes (`reply_expected` and `text`) come last, so a raise leaves the event as Hermes built it. The worst case is Hermes's warning on a thread reply, which is what you get without the plugin.
- A Hermes upgrade that copies the event before the hook, works out `reply_expected` again after it, or renames it, would bring the warning back without any error. So rerun the proof after every Hermes upgrade.
- A message that reaches a conversation while the agent is still answering the one before takes Hermes's busy path, which never runs the hook (`gateway/platforms/base.py:4106-4108`, `gateway/run_busy.py:909`). That message gets no last line, and a `[SILENT]` on it still draws the warning.

## Prove it on your Hermes

```sh
scripts/prove.sh /path/to/hermes-agent [COMMIT] [--suite]
```

It copies Hermes at `COMMIT` (default: the commit above) from your checkout into a temporary folder, without touching the checkout, and runs `tests/hermes/test_zz_quiet_reply_proof.py` there with Hermes's own locked dependencies through [uv](https://docs.astral.sh/uv/). The proof drives Slack events through Hermes's real Slack adapter into `GatewayRunner._handle_message` and the turn, with quiet-reply loaded by Hermes's own plugin discovery, and checks that:

- a "thanks" in the bot's thread is silent, with nothing posted, and the agent gets that reply's own ts;
- DMs, tags (including "@Sam @bot can you two sync?"), the bot's name, reaction triggers and slash commands keep their `reply_expected`, and a `[SILENT]` there still gets the warning;
- a typed answer to a pending clarify question still resolves it (`tests/hermes/test_zz_review_prompts.py`);
- without the plugin enabled, the warning comes back.

It then runs Hermes's own tests of the hook, silence markers, Slack's `reply_expected` and admission with quiet-reply's callback in every dispatch. `--suite` also runs Hermes's whole `tests/gateway` with and without the callback and fails on any test that fails only with it (slow; its logs stay in the folder it prints). Run it with the commit you're upgrading to before you upgrade.

The plugin's own tests need nothing but Python: `python3 -m unittest discover -s tests`.

## License

MIT. See [LICENSE](LICENSE).
