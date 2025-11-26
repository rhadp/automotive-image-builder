#!/bin/bash

echo "[rpmdb] Checking if rpmdb is properly initialized"

# Checking version of glibc package, because it should always be installed
out="$(rpm -q glibc)"
res=$?
if [[ $res -ne 0 ]]; then
    echo "[rpmdb] FAIL: Error accessing rpmdb: $out"
    exit 1
fi

echo "[rpmdb] PASS: rpmdb initialized properly"
