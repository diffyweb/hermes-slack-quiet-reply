#!/usr/bin/env bash
# prove.sh: prove quiet-reply on Hermes's own code, at a Hermes commit.
# Usage: scripts/prove.sh HERMES_CHECKOUT [COMMIT] [--suite]
#   HERMES_CHECKOUT  a git checkout of NousResearch/hermes-agent that holds COMMIT (only read).
#   COMMIT           the Hermes commit to prove against (default: the one this release is proven on, below).
#   --suite          also run Hermes's own tests/gateway twice, with quiet-reply's callback in every
#                    pre_gateway_dispatch (tests/hermes/quiet_reply_everywhere.py) and without, and fail on any test
#                    that fails only with it. Slow: the whole gateway suite, twice.
# It copies Hermes at COMMIT (git archive) into a new temporary folder and runs tests/hermes/test_zz_quiet_reply_proof.py
# there, with Hermes's locked dependencies through uv (https://docs.astral.sh/uv/; the network the first time).
# Rerun it after every Hermes upgrade, against the commit you upgrade to.
set -euo pipefail

PROVEN="bf0203a794a07aac3ff764972ab9087baa4e4f4e"   # Hermes 0.22.5
here=$(cd "$(dirname "$0")/.." && pwd)
[ $# -ge 1 ] || { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
src=$1
shift
commit=$PROVEN suite=0
for arg in "$@"; do
  case "$arg" in --suite) suite=1;; -*) echo "prove.sh: unknown option $arg" >&2; exit 2;; *) commit=$arg;; esac
done
work=$(mktemp -d)
[ "$suite" = 1 ] || trap 'rm -rf "$work"' EXIT   # --suite keeps its logs
echo "--> Hermes ${commit:0:12} into $work"
git -C "$src" archive --format=tar "$commit" | tar -x -C "$work"
cp "$here/tests/hermes/test_zz_quiet_reply_proof.py" "$work/tests/gateway/"
cp "$here/tests/hermes/test_zz_prompt_answers.py" "$work/tests/gateway/"
cp "$here/tests/hermes/test_zz_typed_approval.py" "$work/tests/gateway/"
cp "$here/tests/hermes/test_zz_busy_reply.py" "$work/tests/gateway/"
cp "$here/tests/hermes/quiet_reply_everywhere.py" "$work/"
cd "$work"
export QUIET_REPLY_DIR="$here" UV_PROJECT_ENVIRONMENT="$work/.venv"
hermes_pytest() {
  uv run -q --python "${PYTHON_VERSION:-3.14}" --extra slack --group dev --with pyyaml python -m pytest -p no:cacheprovider "$@"
}

hermes_pytest -q -s tests/gateway/test_zz_quiet_reply_proof.py tests/gateway/test_zz_prompt_answers.py \
  tests/gateway/test_zz_typed_approval.py tests/gateway/test_zz_busy_reply.py
# Hermes's own tests of the hook, silence, Slack's reply_expected and admission, with the callback in every dispatch.
hermes_pytest -q -p quiet_reply_everywhere tests/gateway/test_pre_gateway_dispatch.py \
  tests/gateway/test_gateway_silence_tokens.py tests/gateway/test_slack_reply_expected.py \
  tests/gateway/test_native_admission_metadata.py
[ "$suite" = 1 ] || exit 0

failures() {   # the tests that fail in one run of tests/gateway (not logged errors), sorted: Hermes's suite has its own
  # pytest exits 1 when any test fails; that's expected here, so the two lists are compared instead.
  hermes_pytest -q -rfE "$@" tests/gateway 2>&1 | tee "$work/$label.log" | grep -E '^(FAILED|ERROR) tests/' | sed 's/ - .*//' | sort -u || true
}
finished() {   # a run that stopped before its summary (a collection error, say) proves nothing either way
  grep -qE '[0-9]+ (passed|failed)' "$work/$label.log" || { echo "the $label run didn't finish: $work/$label.log" >&2; exit 1; }
}
label=without; failures > "$work/without.failed"; finished
label=with; failures -p quiet_reply_everywhere > "$work/with.failed"; finished
summary() { grep -E '[0-9]+ (passed|failed)' "$work/$1.log" | tail -n 1; }
echo "--> tests/gateway: $(summary without) without quiet-reply; $(summary with) with it"
new=$(comm -13 "$work/without.failed" "$work/with.failed")
if [ -n "$new" ]; then echo "fail only with quiet-reply:"; echo "$new"; exit 1; fi
echo "no test fails only with quiet-reply ($(wc -l < "$work/without.failed" | tr -d ' ') fail either way: $work/without.failed)"
