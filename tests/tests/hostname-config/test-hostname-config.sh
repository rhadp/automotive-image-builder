#!/usr/bin/bash -x

source $(dirname $BASH_SOURCE)/../../scripts/test-lib.sh

echo_log "Starting build for hostname test..."
build --export tar --extend-define tar_paths=['etc/hostname'] test-hostname.aib.yml out.tar
echo_log "Build completed, output: out.tar"
tar xvf out.tar

HOSTNAME_FILE_PATH="./etc/hostname"
EXPECTED_HOSTNAME='test-host-name-automotive'

# Validate /etc/hostname contains the expected value
assert_has_file "$HOSTNAME_FILE_PATH"
assert_file_has_content "$HOSTNAME_FILE_PATH" "$EXPECTED_HOSTNAME"

echo_pass "hostname has been validated successfully."
