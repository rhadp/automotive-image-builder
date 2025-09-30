#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

echo_log "Starting build for root password test..."
build --export tar --extend-define tar_paths=['etc/shadow'] test-root-password.aib.yml out.tar
echo_log "Build completed, output: out.tar"
tar xvf out.tar

SHADOW_FILE_PATH="./etc/shadow"
EXPECTED_HASH='$6$xoLqEUz0cGGJRx01$H3H/bFm0myJPULNMtbSsOFd/2BnHqHkMD92Sfxd.EKM9hXTWSmELG8cf205l6dktomuTcgKGGtGDgtvHVXSWU.'

# Validate /etc/shadow contains the expected hash for root
assert_has_file "$SHADOW_FILE_PATH"
assert_file_has_content "$SHADOW_FILE_PATH" "root:$EXPECTED_HASH"

echo_pass "root password hash validated successfully."

