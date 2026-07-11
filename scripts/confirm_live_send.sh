#!/usr/bin/env bash
set -euo pipefail

if [[ "${CONFIRMATION:-}" != "SEND TODAY" ]]; then
  echo "::error::Live mode requires confirmation to be exactly: SEND TODAY" >&2
  exit 1
fi

echo "Manual live send confirmed."
