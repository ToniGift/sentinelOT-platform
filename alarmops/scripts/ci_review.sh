#!/bin/sh
# CI review step: replay target-branch rules vs this change, apply the gate,
# post the result as an MR comment, then exit with the gate's result.
set -u
mkdir -p out

if [ -n "${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-}" ]; then
  git fetch --depth=50 origin "+refs/heads/${CI_MERGE_REQUEST_TARGET_BRANCH_NAME}:refs/remotes/origin/${CI_MERGE_REQUEST_TARGET_BRANCH_NAME}" || exit 2
  BASE_REF="origin/${CI_MERGE_REQUEST_TARGET_BRANCH_NAME}"
elif git rev-parse --verify -q HEAD^1 >/dev/null; then
  BASE_REF="HEAD^1"
else
  BASE_REF="HEAD"
fi
echo "Comparing against ${BASE_REF}"

git show "${BASE_REF}:alarms.yaml" > out/base_alarms.yaml || exit 2
python scripts/compare_replay.py --base-rules out/base_alarms.yaml --head-rules alarms.yaml
RC=$?
python scripts/post_mr_comment.py || true
exit "$RC"
