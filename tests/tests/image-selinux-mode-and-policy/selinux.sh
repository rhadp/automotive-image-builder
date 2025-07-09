#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build for selinux_mode and selinux_policy test..."
build --export tar --extend-define tar_paths=['etc/selinux/config'] test-image-selinux.aib.yml out.tar
echo_log "Build completed, output: out.tar"

tar xvf out.tar

SELINUX_CONFIG_PATH="etc/selinux/config"
EXPECTED_MODE="enforcing"
EXPECTED_POLICY="targeted"

# Check selinux config file exists
assert_has_file "$SELINUX_CONFIG_PATH"

# Validate content of the config file
assert_file_has_content "$SELINUX_CONFIG_PATH" "^SELINUX=$EXPECTED_MODE"
assert_file_has_content "$SELINUX_CONFIG_PATH" "^SELINUXTYPE=$EXPECTED_POLICY"

echo_pass "selinux_mode and selinux_policy validated successfully."

