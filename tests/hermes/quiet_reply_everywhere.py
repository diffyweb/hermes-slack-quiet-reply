"""A pytest plugin for Hermes's own test suite: adds quiet-reply's callback to every pre_gateway_dispatch call, as if
the plugin were enabled in every Hermes home. scripts/prove.sh --suite runs Hermes's tests/gateway with it
(pytest -p quiet_reply_everywhere) and without it, and compares the failures. A test that replaces Hermes's hook
dispatch with its own stand-in runs without the callback, as it would with any plugin.
"""
import importlib.util
import os


def pytest_collection_finish(session):
    # After Hermes's tests/conftest.py has sandboxed HERMES_HOME, so importing Hermes here is safe.
    from hermes_cli import plugins

    spec = importlib.util.spec_from_file_location("quiet_reply", os.path.join(os.environ["QUIET_REPLY_DIR"], "__init__.py"))
    quiet_reply = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(quiet_reply)
    real = plugins.ainvoke_hook

    async def ainvoke_hook(hook_name, **kwargs):
        results = await real(hook_name, **kwargs)
        if hook_name == "pre_gateway_dispatch" and kwargs.get("event") is not None:
            extra = quiet_reply.on_dispatch(kwargs["event"])
            if extra is not None:
                results = [*results, extra]
        return results

    plugins.ainvoke_hook = ainvoke_hook
