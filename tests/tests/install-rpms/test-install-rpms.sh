#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build..."
build --distro cs9 --export rpmlist test.aib.yml out.json
echo_log "Build completed, output: out.json"

# Check if rootfs contains 'strace'
echo_log "Checking if rootfs contains 'strace'..."
cat out.json | jq '.rootfs|has("strace")' > has_strace.txt
assert_file_has_content has_strace.txt true
echo_log "Assertion completed for strace."

# Check if rootfs contains 'coreutils-debuginfo'
echo_log "Checking if rootfs contains 'coreutils-debuginfo'..."
cat out.json | jq '.rootfs|has("coreutils-debuginfo")' > has_coreutils_debuginfo.txt
assert_file_has_content has_coreutils_debuginfo.txt true
echo_log "Assertion completed for coreutils-debuginfo."

# Check if rootfs contains 'htop'
echo_log "Checking if rootfs contains 'htop'..."
cat out.json | jq '.rootfs|has("htop")' > has_htop.txt
assert_file_has_content has_htop.txt true
echo_log "Assertion completed for htop."

# Check if qm_rootfs_base contains 'less'
echo_log "Checking if qm_rootfs_base contains 'less'..."
cat out.json | jq '.qm_rootfs_base|has("less")' > qm_has_less.txt
assert_file_has_content qm_has_less.txt true
echo_log "Assertion completed for less."

echo_log "PASS: All package installation checks completed successfully."
