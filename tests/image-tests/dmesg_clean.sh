#!/bin/bash

echo "[dmesg] Checking dmesg for critical errors..."

#TODO: Workaround until the driver gets disabled at the kernel
ALLOWED_WARNING="Warning: (Deprecated|Unmaintained) [Dd]river is detected: nft_compat"

# Run once for debugging logs
dmesg -r -l crit,alert,emerg

# Count the number of lines
if [ "$(dmesg -r -l crit,alert,emerg | grep -Ev "${ALLOWED_WARNING}" -c)" -gt 0 ]; then
  >&2 echo "[dmesg] FAIL: Errors in dmesg detected and marked as critical, alert, or emergency: No critical errors in dmesg."
  exit 1
fi

echo "[dmesg] PASS: No critical errors in dmesg."
