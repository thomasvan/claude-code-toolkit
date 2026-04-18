#!/usr/bin/env bash
# Sync your fork's main branch with the upstream repository.
# Usage: ./scripts/sync-fork.sh [branch]  (default: main)

set -euo pipefail

BRANCH="${1:-main}"

echo "==> Fetching upstream..."
git fetch upstream

echo "==> Switching to $BRANCH..."
git checkout "$BRANCH"

echo "==> Rebasing onto upstream/$BRANCH..."
git rebase "upstream/$BRANCH"

echo "==> Pushing to origin/$BRANCH..."
git push origin "$BRANCH"

echo "✓ Fork is up to date with upstream/$BRANCH"
