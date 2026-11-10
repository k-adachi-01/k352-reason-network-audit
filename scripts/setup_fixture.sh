#!/bin/sh
# Recreate the delegation fixture as a git repo with the bug committed.
set -eu
cd "$(dirname "$0")/../fixtures/k352-repo"
[ -d .git ] || git init -q
git add -A
git -c user.email=audit@example.com -c user.name=audit commit -qm "fixture: buggy calc for K-352 delegation test" --allow-empty
python3 -m unittest -v 2>&1 | tail -4
