#!/usr/bin/bash -x

source "$(dirname ${BASH_SOURCE[0]})"/../../scripts/test-lib.sh

TAR_FILE="out.tar"

# Update cleanup function parameters on each test artifact change
trap 'cleanup_path "$TAR_FILE" "usr"' 'EXIT'

echo_log "Starting build..."
build --export bootc-tar \
    --extend-define tar_paths=['usr/sbin','usr/lib/qm/rootfs/usr/sbin'] \
    remove-files.aib.yml \
    "$TAR_FILE"
echo_log "Build completed, output: $TAR_FILE"

echo_log "Extracting $TAR_FILE..."
tar xvf "$TAR_FILE"

# Define the extracted content directories for validation
EXTRACTED_DIR="./usr"
QM_EXTRACTED_DIR="./usr/lib/qm/rootfs"

# Files crond and cupsd should be removed by remove_files
echo_log "Checking files in content section..."
assert_not_has_file "$EXTRACTED_DIR/sbin/crond"

echo_log "Checking files in qm.content section..."
assert_not_has_file "$QM_EXTRACTED_DIR/usr/sbin/cupsd"

echo_pass "The remove_files directive correctly removed specified files."
