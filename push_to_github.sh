#!/usr/bin/env bash
# Push meta_hackathon_2026/ to public GitHub repo (META-02).
# Usage: GITHUB_REPO=deliciosoradha/tattvaswarm ./push_to_github.sh
set -euo pipefail
REPO="${GITHUB_REPO:-deliciosoradha/tattvaswarm}"
BRANCH="${BRANCH:-main}"

if [ ! -d .git ]; then
  git init -b "$BRANCH"
  git remote add origin "https://github.com/${REPO}.git" 2>/dev/null || true
fi
git add README.md meta_hackathon_2026 tests .gitignore push_to_github.sh 2>/dev/null || true
git add logs/meta_credit_ledger.json 2>/dev/null || true
git commit -m "Meta Hackathon 2026: Shiva Router x Tattva Swarm (New Work Only)" || echo "nothing to commit"
git push -u origin "$BRANCH"
echo "OK: pushed to https://github.com/${REPO}"
