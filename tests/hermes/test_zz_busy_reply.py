# A reply that arrives while the session's turn is still running goes through pre_gateway_dispatch too, so it gets the
# line. With the session authority every real gateway builds at start (gateway/run_bootstrap.py:811-813), busy input
# goes through dispatch_busy_burst (gateway/platforms/base.py:4059-4062) into GatewayRunner._handle_message, which
# runs the hook. Run by scripts/prove.sh.
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from tests.gateway.test_zz_quiet_reply_proof import ALICE, CHANNEL, THREAD, rig


@pytest.mark.asyncio
async def test_a_reply_while_the_session_is_busy_still_runs_the_hook(tmp_path, monkeypatch):
    r, _ = await rig(tmp_path, monkeypatch, reacts=False)
    try:
        r.adapter._mentioned_threads.add(THREAD)
        src = r.adapter.build_source(chat_id=CHANNEL, chat_type="group", user_id=ALICE, thread_id=THREAD)
        adapter_key = r.adapter._source_session_key(src)
        r.adapter._active_sessions[adapter_key] = asyncio.Event()   # the adapter thinks a turn is running
        event = {"channel": CHANNEL, "channel_type": "channel", "user": ALICE, "text": "thanks!",
                 "ts": "1799000000.000700", "thread_ts": THREAD}
        with patch.object(r.adapter, "_resolve_user_name", new=AsyncMock(return_value="Alice")), \
                patch.object(r.adapter, "_resolve_channel_name", new=AsyncMock(return_value="general")), \
                patch.object(r.adapter, "_fetch_thread_context", new=AsyncMock(return_value=None)), \
                patch.object(r.adapter, "_fetch_thread_parent_text", new=AsyncMock(return_value="")), \
                patch.object(r.adapter, "_has_active_session_for_thread", return_value=False):
            task = asyncio.create_task(r.adapter._handle_slack_message(event))
            for _ in range(100):
                if r.hooked:
                    break
                await asyncio.sleep(0.05)
            task.cancel()
        print(f"\n  busy: shared runtime owns input {r.adapter._shared_runtime_owns_input(r.hooked[0]) if r.hooked else None}; "
              f"hook ran {len(r.hooked)}x; text after the hook {[getattr(e, 'text', None) for e in r.hooked]!r}; "
              f"reply_expected {[getattr(e, 'reply_expected', None) for e in r.hooked]!r}")
        assert r.hooked
    finally:
        r.adapter._active_sessions.clear()
        r.close()
