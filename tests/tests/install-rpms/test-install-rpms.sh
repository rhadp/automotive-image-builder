#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build..."
build --export rpmlist test.aib.yml out.json
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

# Check if qm_rootfs_base contains 'rpm-debuginfo'
echo_log "Checking if qm_rootfs_base contains 'rpm-debuginfo'..."
cat out.json | jq '.qm_rootfs_base|has("rpm-debuginfo")' > qm_has_rpm_debuginfo.txt
assert_file_has_content qm_has_rpm_debuginfo.txt true
echo_log "Assertion completed for rpm-debuginfo."

# Check if qm_rootfs_base contains 'neofetch'
echo_log "Checking if qm_rootfs_base contains 'neofetch'..."
cat out.json | jq '.qm_rootfs_base|has("neofetch")' > qm_has_neofetch.txt
assert_file_has_content qm_has_neofetch.txt true
echo_log "Assertion completed for neofetch."

echo_pass "All package installation checks completed successfully."
