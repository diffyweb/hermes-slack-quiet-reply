# Changelog

## 0.1.1 (2026-10-31)

- The warning about a moved Hermes internal is logged once per process, not on every Slack message.
- README: the command examples now read `!new` and `restart gateway` typed in a DM.
- README and docstring: a message that arrives mid-turn is steered, queued or interrupts the running turn, as `display.busy_input_mode` says.

## 0.1.0 (2026-10-31)

First release, proven on Hermes 0.22.5 (`bf0203a794`). On Slack, a plain thread reply the agent answers with `[SILENT]` posts nothing instead of Hermes's silence warning, and each Slack message the agent reads ends with a line naming its ts and channel, and whether it tags or names the agent.
