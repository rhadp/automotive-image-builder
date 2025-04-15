#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export rpmlist test.aib.yml out.json
echo_log "Build completed, output: out.json"

echo_log "Checking if rootfs contains 'strace'..."
cat out.json | jq '.rootfs|has("strace")' > has_strace.txt
echo_log "Extracted strace check result to has_strace.txt"
assert_file_has_content has_strace.txt true
echo_log "Assertion completed for has_strace.txt"

echo_log "Checking if qm_rootfs_base contains 'less'..."
cat out.json | jq '.qm_rootfs_base|has("less")' > qm_has_less.txt
echo_log "Extracted less check result to qm_has_less.txt"
assert_file_has_content qm_has_less.txt true
echo_log "Assertion completed for qm_has_less.txt"

