#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

TAR_FILE="out.tar"

# Update cleanup function parameters on each test artifact change
trap 'cleanup_path "$TAR_FILE" "etc"' 'EXIT'

echo_log "Starting build for root password test..."
build --export bootc-tar \
    --extend-define tar_paths=['etc/shadow'] \
    root-password.aib.yml \
    "$TAR_FILE"
echo_log "Build completed, output: $TAR_FILE"

echo_log "Extracting $TAR_FILE..."
tar xvf "$TAR_FILE"

SHADOW_FILE_PATH="./etc/shadow"
EXPECTED_HASH='$6$xoLqEUz0cGGJRx01$H3H/bFm0myJPULNMtbSsOFd/2BnHqHkMD92Sfxd.EKM9hXTWSmELG8cf205l6dktomuTcgKGGtGDgtvHVXSWU.'

# Validate /etc/shadow contains the expected hash for root
assert_has_file "$SHADOW_FILE_PATH"
chmod a+r "$SHADOW_FILE_PATH"
assert_file_has_content "$SHADOW_FILE_PATH" "root:$EXPECTED_HASH"

echo_pass "root password hash validated successfully."

