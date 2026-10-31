# Reviewer's end-to-end check (copy into tests/hermes beside the proof) that a typed answer to a pending clarify still resolves it
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from tests.gateway.test_zz_quiet_reply_proof import ALICE, CHANNEL, THREAD, rig
from tools import clarify_gateway


@pytest.mark.asyncio
@pytest.mark.parametrize("typed, expected", [("2", "prod"), ("prod", "prod")])
async def test_a_typed_clarify_answer_in_the_thread_resolves_it(tmp_path, monkeypatch, typed, expected):
    r, _ = await rig(tmp_path, monkeypatch, reacts=False)
    try:
        r.adapter._mentioned_threads.add(THREAD)
        src = r.adapter.build_source(chat_id=CHANNEL, chat_type="group", user_id=ALICE, thread_id=THREAD)
        key = r.runner._session_key_for_source(src)
        entry = clarify_gateway.register("cq1", key, "Which site?", ["staging", "prod"])
        event = {"channel": CHANNEL, "channel_type": "channel", "user": ALICE, "text": typed,
                 "ts": "1799000000.000500", "thread_ts": THREAD}
        with patch.object(r.adapter, "_resolve_user_name", new=AsyncMock(return_value="Alice")), \
                patch.object(r.adapter, "_resolve_channel_name", new=AsyncMock(return_value="general")), \
                patch.object(r.adapter, "_fetch_thread_context", new=AsyncMock(return_value=None)), \
                patch.object(r.adapter, "_fetch_thread_parent_text", new=AsyncMock(return_value="")), \
                patch.object(r.adapter, "_has_active_session_for_thread", return_value=False):
            await r.adapter._handle_slack_message(event)
            for _ in range(200):
                if entry.event.is_set() or r.turns:
                    break
                await asyncio.sleep(0.05)
        print(f"\n  typed {typed!r}: clarify response {entry.response!r}; agent turns {r.turns}")
        assert entry.response == expected and not r.turns
    finally:
        clarify_gateway.clear_session(key)
        r.close()
