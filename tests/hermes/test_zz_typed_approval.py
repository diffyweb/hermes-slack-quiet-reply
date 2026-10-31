# A bare "yes" typed in the bot's thread while the agent waits on a dangerous-command approval approves it, with and
# without the plugin. Hermes matches that text after pre_gateway_dispatch (gateway/run_inbound.py:1223-1224,
# gateway/run_busy.py:633-635), so quiet-reply must leave it alone. Run by scripts/prove.sh.
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from tests.gateway.test_zz_quiet_reply_proof import ALICE, CHANNEL, THREAD, rig
from tools import approval as approval_mod
from tools.approval_gateway_wait import _ApprovalEntry


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_a_typed_yes_to_a_blocking_approval_in_the_thread_approves_it(tmp_path, monkeypatch, enabled):
    r, _ = await rig(tmp_path, monkeypatch, enabled=enabled, reacts=False)
    key = None
    try:
        r.adapter._mentioned_threads.add(THREAD)
        src = r.adapter.build_source(chat_id=CHANNEL, chat_type="group", user_id=ALICE, thread_id=THREAD)
        key = r.runner._session_key_for_source(src)
        entry = _ApprovalEntry({"command": "rm -rf build"})
        approval_mod._gateway_queues.setdefault(key, []).append(entry)
        real_running = r.runner._is_session_running
        monkeypatch.setattr(r.runner, "_is_session_running", lambda k: k == key or real_running(k))
        event = {"channel": CHANNEL, "channel_type": "channel", "user": ALICE, "text": "yes",
                 "ts": "1799000000.000600", "thread_ts": THREAD}
        with patch.object(r.adapter, "_resolve_user_name", new=AsyncMock(return_value="Alice")), \
                patch.object(r.adapter, "_resolve_channel_name", new=AsyncMock(return_value="general")), \
                patch.object(r.adapter, "_fetch_thread_context", new=AsyncMock(return_value=None)), \
                patch.object(r.adapter, "_fetch_thread_parent_text", new=AsyncMock(return_value="")), \
                patch.object(r.adapter, "_has_active_session_for_thread", return_value=False):
            await r.adapter._handle_slack_message(event)
            for _ in range(100):
                if entry.event.is_set() or r.turns:
                    break
                await asyncio.sleep(0.05)
        hooked = [getattr(e, "text", None) for e in r.hooked]
        print(f"\n  plugin enabled {enabled}: hook passed on {hooked!r}; approval result {entry.result!r}; "
              f"turns {r.turns}; posted {r.sent}")
        assert entry.result == "once"
    finally:
        approval_mod._gateway_queues.pop(key, None)
        r.close()
