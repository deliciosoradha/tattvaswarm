#!/usr/bin/env bash
# Pre-push sanitization scan for the public TattvaSwarm repository.
# Fails loudly if likely secrets, PII patterns, private paths or wallet
# addresses are found in tracked or untracked files.
#
# Usage:  bash scripts/sanitize_check.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

PATTERNS=(
  'sk-[A-Za-z0-9_-]{20,}'                       # generic API keys
  'v1\.[A-Za-z0-9_.-]{60,}'                     # Nebius key style
  'NEBIUS_API_KEY=[A-Za-z0-9]'                  # non-empty assignment
  'TAVILY_API_KEY=[A-Za-z0-9]'                  # non-empty assignment
  'glpat-[A-Za-z0-9_-]{10,}'                    # GitLab PAT
  'BEGIN [A-Z ]*PRIVATE KEY'                    # private keys
  'password[[:space:]]*=[[:space:]]*[^[:space:]#]'  # password assignments
  '0x[0-9a-fA-F]{40}'                           # wallet addresses
  '/home/delideli'                              # private host paths
  '(^|[^0-9])192\.168\.[0-9]'                   # private IPs (192.168.x)
  '(^|[^0-9])10\.[0-9]{1,3}\.[0-9]{1,3}\.'      # private IPs (10.x)
  'notification_email|smtp_url'                 # service credentials
)

echo "sanitize_check: scanning repository (tracked + untracked)…"
FAIL=0
for pat in "${PATTERNS[@]}"; do
  hits=$(git grep -nEI --untracked -- "$pat" 2>/dev/null | grep -v 'scripts/sanitize_check.sh' || true)
  if [ -n "$hits" ]; then
    echo "[HIT] pattern: $pat"
    echo "$hits" | head -10
    FAIL=1
  fi
done

if [ "$FAIL" -eq 0 ]; then
  echo "sanitize_check: CLEAN — no findings"
else
  echo "sanitize_check: FINDINGS — fix before pushing"
fi
exit "$FAIL"
